# Minimal double-entry ledger engine used for the GAAP leg of the
# reconciliation identity run.  Amounts are Decimal (exact); every entry is
# verified balanced (sum of debits == sum of credits) before posting.
#
# Account normal balances:
#   Asset, Expense  -> debit  normal (balance > 0 = debit)
#   Liability, Equity, Income -> credit normal (balance < 0 = debit)
from decimal import Decimal

DEBIT_NORMAL = {"Asset", "Expense"}
CREDIT_NORMAL = {"Liability", "Equity", "Income"}


class LedgerError(Exception):
    pass


class BAMLedger:
    def __init__(self):
        self.accounts = {}
        self.journal = []

    def add(self, name, atype):
        if atype not in DEBIT_NORMAL | CREDIT_NORMAL:
            raise LedgerError(f"unknown account type {atype}")
        self.accounts[name] = {"type": atype, "balance": Decimal("0")}
        return self

    def post(self, date, desc, lines):
        """lines: list of (account, debit, credit) Decimal-able triples.

        Type-aware accumulation: a debit increases the balance of a debit-normal
        account (Asset/Expense) and decreases a credit-normal one (Liability/
        Equity/Income).  The entry as a whole must still satisfy sum(debit) ==
        sum(credit)."""
        total = Decimal("0")
        posted = []
        for acct, debit, credit in lines:
            debit = Decimal(str(debit))
            credit = Decimal(str(credit))
            if debit < 0 or credit < 0:
                raise LedgerError(f"negative amounts in {desc}")
            if (debit == 0) == (credit == 0):
                raise LedgerError(f"non-strict posting in {desc}: {acct}")
            if acct not in self.accounts:
                raise LedgerError(f"account not opened: {acct}")
            if self.accounts[acct]["type"] in DEBIT_NORMAL:
                self.accounts[acct]["balance"] += debit - credit
            else:
                self.accounts[acct]["balance"] += credit - debit
            total += debit - credit
            posted.append((acct, debit, credit))
        if total != 0:
            raise LedgerError(f"UNBALANCED entry '{desc}': debits != credits by {total}")
        self.journal.append((date, desc, posted))
        return self

    def bal(self, name):
        return self.accounts[name]["balance"]

    def trial_balance(self):
        """Return (dr_total, cr_total, balanced).  Positive balance of a
        debit-normal account is a debit; negative balance of a credit-normal
        account is likewise a debit; mirror for credits."""
        total_dr = Decimal("0")
        total_cr = Decimal("0")
        for name, acct in self.accounts.items():
            b = acct["balance"]
            if acct["type"] in DEBIT_NORMAL:
                if b > 0:
                    total_dr += b
                elif b < 0:
                    total_cr += -b
            else:
                if b > 0:
                    total_cr += b
                elif b < 0:
                    total_dr += -b
        return total_dr, total_cr, total_dr == total_cr

    def income_statement(self, income_accounts, expense_accounts):
        """Return dict of line totals and net income."""
        lines = {}
        total_income = Decimal("0")
        total_expense = Decimal("0")
        for a in income_accounts:
            b = self.accounts[a]["balance"]
            lines[a] = b
            total_income += b
        for a in expense_accounts:
            b = self.accounts[a]["balance"]
            lines[a] = -b  # expense as positive cost
            total_expense += -b
        return {"lines": lines, "income": total_income, "expense": total_expense,
                "net_income": total_income - total_expense}

    def balances_by_type(self):
        """Balance-sheet side totals by account type."""
        out = {}
        for name, acct in self.accounts.items():
            out.setdefault(acct["type"], Decimal("0"))
            out[acct["type"]] += acct["balance"]
        return out

    def close_period(self, income_accounts, expense_accounts, retained_acct, date):
        """Close every P&L account to retained earnings with ordinary
        (conventional-sign) entries, leaving each closed account at zero.
        Returns net income with the sign convention profit > 0.

        For a credit-normal income account with positive balance b:
            debit the account by b, credit retained by b.
        For a debit-normal expense account with positive balance b:
            credit the account by b, debit retained by b.
        Negative balances (contra / over-absorbed) are mirrored."""
        ni = Decimal("0")
        for a in income_accounts:
            b = self.accounts[a]["balance"]
            ni += b
            if b > 0:
                self.post(date, f"close {a}", [(a, b, 0), (retained_acct, 0, b)])
            elif b < 0:
                self.post(date, f"close {a}", [(a, 0, -b), (retained_acct, -b, 0)])
        for a in expense_accounts:
            b = self.accounts[a]["balance"]
            ni -= b
            if b > 0:
                self.post(date, f"close {a}", [(a, 0, b), (retained_acct, b, 0)])
            elif b < 0:
                self.post(date, f"close {a}", [(a, -b, 0), (retained_acct, 0, -b)])
        return ni