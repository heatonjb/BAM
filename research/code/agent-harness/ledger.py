"""Minimum-viable append-only ledger with typed accounts and fail-closed invariants.

All amounts are integer minor units (cents). No floats are used anywhere.
Balances use a single "debit-positive signed" convention:
    v(account) = sum(debit amounts) - sum(credit amounts)
so asset balances are positive, liability/equity/revenue balances are negative,
and expense balances are positive.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

MINOR_UNITS = 100

CLASSES = ("asset", "liability", "equity", "revenue", "expense")
NORMAL_DEBIT = {"asset": True, "expense": True,
                "liability": False, "equity": False, "revenue": False}


class LedgerError(Exception):
    pass


class UnbalancedEntry(LedgerError):
    pass


class DuplicateEntry(LedgerError):
    pass


class InvariantViolation(LedgerError):
    pass


@dataclass(frozen=True)
class Account:
    id: str
    name: str
    cls: str
    contra: bool = False
    currency: str = "USD"

    def __post_init__(self):
        if self.cls not in CLASSES:
            raise LedgerError(f"unknown account class {self.cls!r}")


@dataclass(frozen=True)
class Posting:
    account: str
    amount: int
    side: str

    def __post_init__(self):
        if self.side not in ("debit", "credit"):
            raise LedgerError(f"bad side {self.side!r}")
        if not isinstance(self.amount, int) or self.amount <= 0:
            raise LedgerError(f"amount must be a positive int, got {self.amount!r}")

    def signed(self) -> int:
        return self.amount if self.side == "debit" else -self.amount


@dataclass
class Entry:
    id: str
    date: _dt.date
    postings: List[Posting]
    kind: str = "txn"
    memo: str = ""
    reversal_of: Optional[str] = None
    meta: dict = field(default_factory=dict)


class Ledger:
    def __init__(self) -> None:
        self.accounts: Dict[str, Account] = {}
        self.entries: List[Entry] = []
        self._ids: set = set()
        self.closes: List[dict] = []

    def add_account(self, account: Account) -> Account:
        if account.id in self.accounts:
            raise LedgerError(f"duplicate account {account.id}")
        self.accounts[account.id] = account
        return account

    def account(self, aid: str) -> Account:
        return self.accounts[aid]

    def of_class(self, cls: str) -> List[str]:
        return [a.id for a in self.accounts.values() if a.cls == cls]

    def post(self, entry: Entry) -> Entry:
        if entry.id in self._ids:
            raise DuplicateEntry(entry.id)
        for p in entry.postings:
            if p.account not in self.accounts:
                raise LedgerError(f"unknown account {p.account}")
        self.check_entry_balanced(entry)
        self.entries.append(entry)
        self._ids.add(entry.id)
        return entry

    def reverse(self, entry_id: str, date: _dt.date, new_id: str) -> Entry:
        original = next(e for e in self.entries if e.id == entry_id)
        flipped = [Posting(p.account, p.amount,
                           "credit" if p.side == "debit" else "debit")
                   for p in original.postings]
        entry = Entry(new_id, date, flipped, kind="reverse",
                      memo=f"reversal of {entry_id}", reversal_of=entry_id)
        return self.post(entry)

    # ------------------------------------------------------------------ #
    # invariant 1: per-entry debits == credits (fail-closed at write time)
    # ------------------------------------------------------------------ #
    @staticmethod
    def check_entry_balanced(entry: Entry) -> None:
        debits = sum(p.amount for p in entry.postings if p.side == "debit")
        credits = sum(p.amount for p in entry.postings if p.side == "credit")
        if debits != credits:
            raise UnbalancedEntry(
                f"entry {entry.id}: debits {debits} != credits {credits}")

    # ------------------------------------------------------------------ #
    # balances
    # ------------------------------------------------------------------ #
    def balance(self, aid: str, on_or_before: Optional[_dt.date] = None) -> int:
        total = 0
        for e in self.entries:
            if on_or_before is not None and e.date > on_or_before:
                continue
            for p in e.postings:
                if p.account == aid:
                    total += p.signed()
        return total

    def flow(self, aid: str, start_excl: _dt.date, end_incl: _dt.date,
             kinds: Tuple[str, ...] = ("txn",)) -> int:
        total = 0
        for e in self.entries:
            if e.kind not in kinds:
                continue
            if e.date <= start_excl or e.date > end_incl:
                continue
            for p in e.postings:
                if p.account == aid:
                    total += p.signed()
        return total

    # ------------------------------------------------------------------ #
    # invariant 2: trial balance (global roll-up sums to zero)
    # ------------------------------------------------------------------ #
    def check_trial_balance(self, as_of: _dt.date) -> int:
        total = sum(self.balance(a.id, as_of) for a in self.accounts.values())
        if total != 0:
            raise InvariantViolation(
                f"trial balance not zero at {as_of}: {total}")
        return total

    # ------------------------------------------------------------------ #
    # invariant 3: balance sheet equation A = L + E
    # ------------------------------------------------------------------ #
    def balance_sheet_equation(self, as_of: _dt.date) -> Tuple[int, int, int, int]:
        assets = sum(self.balance(a, as_of) for a in self.of_class("asset"))
        liabilities = -sum(self.balance(a, as_of) for a in self.of_class("liability"))
        equity = -sum(self.balance(a, as_of)
                      for a in (self.of_class("equity")
                                + self.of_class("revenue")
                                + self.of_class("expense")))
        residual = assets - (liabilities + equity)
        if residual != 0:
            raise InvariantViolation(
                f"A != L + E at {as_of}: A={assets} L={liabilities} E={equity}")
        return assets, liabilities, equity, residual

    # ------------------------------------------------------------------ #
    # invariant 4: retained-earnings roll-forward (checked at close time)
    # ------------------------------------------------------------------ #
    def check_retained_earnings(self) -> dict:
        if not self.closes:
            raise InvariantViolation("no closes recorded")
        last = self.closes[-1]
        expected = last["re_before"] + last["net_income"] - last["dividends"]
        if last["re_after"] != expected:
            raise InvariantViolation(
                f"RE roll-forward broken: {last['re_after']} != {expected}")
        return last


def money(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}{cents // 100}.{cents % 100:02d}"
