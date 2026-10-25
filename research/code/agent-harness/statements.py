"""Projection layer: emit the three statements + KPIs as pure functions of the journal,
plus period-close mechanics (new immutable closing entries)."""
from __future__ import annotations

import datetime as _dt
from typing import Dict, List, Tuple

from ledger import Account, Entry, Ledger, Posting

CHART = {
    "Cash":          ("Cash and equivalents", "asset", False),
    "AR":            ("Accounts receivable", "asset", False),
    "Prepaid":       ("Prepaid expenses", "asset", False),
    "Inventory":     ("Inventory", "asset", False),
    "PPE":           ("Property, plant & equipment (gross)", "asset", False),
    "AccumDep":      ("Accumulated depreciation", "asset", True),
    "AP":            ("Accounts payable", "liability", False),
    "Accrued":       ("Accrued liabilities", "liability", False),
    "DeferredRev":   ("Deferred revenue", "liability", False),
    "TaxPayable":    ("Income tax payable", "liability", False),
    "InterestPay":   ("Interest payable", "liability", False),
    "Debt":          ("Debt", "liability", False),
    "CommonStock":   ("Common stock", "equity", False),
    "RetainedEarn":  ("Retained earnings", "equity", False),
    "Dividends":     ("Dividends declared", "equity", True),
    "Revenue":       ("Revenue", "revenue", False),
    "COGS":          ("Cost of goods sold", "expense", False),
    "SalariesExp":   ("Salaries expense", "expense", False),
    "RentExp":       ("Rent expense", "expense", False),
    "DepExp":        ("Depreciation expense", "expense", False),
    "InterestExp":   ("Interest expense", "expense", False),
    "TaxExp":        ("Income tax expense", "expense", False),
}

IS_ORDER = ["Revenue", "COGS", "SalariesExp", "RentExp", "DepExp",
            "InterestExp", "TaxExp"]
BS_ORDER_A = ["Cash", "AR", "Prepaid", "Inventory", "PPE", "AccumDep"]
BS_ORDER_L = ["AP", "Accrued", "DeferredRev", "TaxPayable", "InterestPay",
              "Debt"]
BS_ORDER_E = ["CommonStock", "RetainedEarn", "Dividends"]


def build_chart(ledger: Ledger) -> None:
    for aid, (name, cls, contra) in CHART.items():
        ledger.add_account(Account(aid, name, cls, contra=contra))


def income_statement(ledger: Ledger, start_excl: _dt.date,
                     end_incl: _dt.date) -> Dict[str, int]:
    """Revenue and expense balances are negative/positive in signed form; flip to
    statement-positive presentation."""
    out: Dict[str, int] = {}
    for aid in IS_ORDER:
        if aid not in ledger.accounts:
            out[aid] = 0
            continue
        v = ledger.flow(aid, start_excl, end_incl, kinds=("txn",))
        out[aid] = -v if ledger.account(aid).cls == "revenue" else v
    rev_total = -sum(ledger.flow(a, start_excl, end_incl, kinds=("txn",))
                     for a in ledger.of_class("revenue"))
    exp_total = sum(ledger.flow(a, start_excl, end_incl, kinds=("txn",))
                    for a in ledger.of_class("expense"))
    revenue = rev_total
    cogs = out["COGS"]
    gross_profit = revenue - cogs
    opex = exp_total - cogs
    ebit = gross_profit - opex
    pretax = ebit
    net_income = rev_total - exp_total
    out.update(Revenue=rev_total, gross_profit=gross_profit, opex=opex,
               ebit=ebit, pretax=pretax, net_income=net_income)
    return out


def balance_sheet(ledger: Ledger, as_of: _dt.date) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for aid in BS_ORDER_A:
        v = ledger.balance(aid, as_of)
        out[aid] = -v if ledger.account(aid).contra else v
    for aid in BS_ORDER_L:
        out[aid] = -ledger.balance(aid, as_of)
    for aid in BS_ORDER_E:
        v = ledger.balance(aid, as_of)
        out[aid] = -v if ledger.account(aid).contra else -v
    total_assets = sum(out[a] for a in BS_ORDER_A)
    total_liabilities = sum(out[a] for a in BS_ORDER_L)
    total_equity = sum(out[a] for a in BS_ORDER_E)
    out.update(total_assets=total_assets, total_liabilities=total_liabilities,
               total_equity=total_equity)
    return out


def cash_flow(ledger: Ledger, start_excl: _dt.date,
              end_incl: _dt.date) -> Dict[str, int]:
    """Indirect method. Every balance-sheet delta that carries a cash effect is
    enumerated so the reconciliation is exact."""
    is_ = income_statement(ledger, start_excl, end_incl)
    ni = is_["net_income"]
    dep = is_["DepExp"]

    def d(aid: str) -> int:
        """Change in the normal-positive amount of an account over the period."""
        raw = ledger.balance(aid, end_incl) - ledger.balance(aid, start_excl)
        flip = ledger.account(aid).cls in ("liability", "equity")
        return -raw if flip else raw

    ocf = (ni + dep
           - d("AR") - d("Inventory") - d("Prepaid")
           + d("AP") + d("Accrued") + d("DeferredRev")
           + d("TaxPayable") + d("InterestPay"))
    icf = -d("PPE")
    div_paid = ledger.flow("Dividends", start_excl, end_incl, kinds=("txn",))
    fcf = d("Debt") + d("CommonStock") - div_paid

    cash_beg = ledger.balance("Cash", start_excl)
    net_change = ocf + icf + fcf
    cash_end = cash_beg + net_change
    return dict(operating=ocf, investing=icf, financing=fcf,
                net_change=net_change, cash_begin=cash_beg,
                cash_end=cash_end, net_income=ni, depreciation=dep)


def check_cash_flow_articulation(ledger: Ledger, start_excl: _dt.date,
                                 end_incl: _dt.date) -> Dict[str, int]:
    cf = cash_flow(ledger, start_excl, end_incl)
    bs_cash = ledger.balance("Cash", end_incl)
    if cf["cash_end"] != bs_cash:
        raise AssertionError(
            f"cash-flow terminal {cf['cash_end']} != balance-sheet cash {bs_cash}")
    return cf


def kpis(ledger: Ledger, start_excl: _dt.date, end_incl: _dt.date) -> Dict[str, float]:
    is_ = income_statement(ledger, start_excl, end_incl)
    bs = balance_sheet(ledger, end_incl)
    rev = is_["Revenue"]
    cogs = is_["COGS"]
    out: Dict[str, float] = {}
    out["gross_margin"] = (rev - cogs) / rev if rev else float("nan")
    out["net_margin"] = is_["net_income"] / rev if rev else float("nan")
    out["current_ratio"] = ((bs["Cash"] + bs["AR"] + bs["Prepaid"] + bs["Inventory"])
                            / max(1, bs["AP"] + bs["Accrued"] + bs["DeferredRev"]
                                  + bs["TaxPayable"] + bs["InterestPay"]))
    out["working_capital"] = (bs["Cash"] + bs["AR"] + bs["Prepaid"] + bs["Inventory"]
                              - bs["AP"] - bs["Accrued"] - bs["DeferredRev"]
                              - bs["TaxPayable"] - bs["InterestPay"])
    days = max(1, (end_incl - start_excl).days)
    out["dso"] = (bs["AR"] / rev * days) if rev else float("nan")
    out["dio"] = (bs["Inventory"] / cogs * days) if cogs else float("nan")
    out["dpo"] = (bs["AP"] / cogs * days) if cogs else float("nan")
    out["ccc"] = out["dso"] + out["dio"] - out["dpo"]
    out["cash"] = float(bs["Cash"])
    out["runway_months"] = (bs["Cash"] / is_["opex"]
                            if is_["opex"] else float("inf"))
    out["return_on_equity"] = (is_["net_income"] / bs["total_equity"]
                               if bs["total_equity"] else float("nan"))
    return out


def close_period(ledger: Ledger, start_excl: _dt.date, end_incl: _dt.date,
                 entry_id: str) -> dict:
    """Close by emitting a new immutable entry that zeroes temporary accounts and
    rolls net income less dividends into retained earnings."""
    is_ = income_statement(ledger, start_excl, end_incl)
    rev_bal = ledger.balance("Revenue", end_incl)          # negative
    exp_ids = [a for a in ledger.of_class("expense")]
    div_bal = ledger.balance("Dividends", end_incl)        # positive (debit)
    postings: List[Posting] = []
    for aid in ledger.of_class("revenue"):
        v = ledger.balance(aid, end_incl)
        if v != 0:
            postings.append(Posting(aid, -v, "debit"))
    for aid in exp_ids:
        v = ledger.balance(aid, end_incl)
        if v != 0:
            postings.append(Posting(aid, v, "credit"))
    if div_bal != 0:
        postings.append(Posting("Dividends", div_bal, "credit"))
    net_to_re = is_["net_income"] - (div_bal)
    re_before = -ledger.balance("RetainedEarn", end_incl)
    if net_to_re != 0:
        postings.append(Posting("RetainedEarn", abs(net_to_re),
                                "credit" if net_to_re >= 0 else "debit"))
    if postings:
        entry = Entry(entry_id, end_incl, postings, kind="close",
                      memo=f"close {start_excl}..{end_incl}")
        ledger.post(entry)
    re_after = -ledger.balance("RetainedEarn", end_incl)
    record = dict(period_end=end_incl, re_before=re_before, re_after=re_after,
                  net_income=is_["net_income"], dividends=div_bal,
                  entry_id=entry_id)
    ledger.closes.append(record)
    return record
