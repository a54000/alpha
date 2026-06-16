#!/usr/bin/env python3
"""Run feature validation and generate report.

This script validates that features_daily values match independently
recomputed indicator values from prices_daily.

Usage:
    PYTHONPATH=. python scripts/run_feature_validation.py
"""

from __future__ import annotations

from datetime import date

from app.research.feature_validation import FeatureValidator, ValidationStatus
from db.session import build_session_factory


def main() -> int:
    """Run feature validation and generate report."""
    session_factory = build_session_factory()
    validator = FeatureValidator(session_factory)
    
    print("Running feature validation...")
    print(f"Validating indicators: rsi_14, macd, macd_signal, macd_hist, adx_14, atr_14, bb_width, ema_5, ema_13, ema_20, ema_50, ema_150, ema_200")
    print("-" * 80)
    
    # Run validation with original methodology
    results = validator.run_validation(
        symbol_count=10,
        date_count=5,
        months_back=6,
    )
    
    # Print results
    for indicator_name, result in results.items():
        print(f"\n{indicator_name}:")
        print(f"  Status: {result.status.value}")
        print(f"  Sample Count: {result.sample_count}")
        print(f"  Mean Absolute Error: {result.mean_absolute_error:.6f}")
        print(f"  Max Absolute Error: {result.max_absolute_error:.6f}")
        print(f"  Match Percentage: {result.match_percentage:.2f}%")
        if result.mismatches:
            print(f"  Mismatches: {len(result.mismatches)}")
    
    # Generate report
    generate_report(results)
    
    print("\n" + "-" * 80)
    print("Validation complete. Report generated: docs/FEATURE_VALIDATION_REPORT.md")
    
    return 0


def generate_report(results: dict[str, any]) -> None:
    """Generate markdown report from validation results.
    
    Args:
        results: Dictionary of indicator validation results
    """
    report_lines = [
        "# Feature Validation Report",
        "",
        f"**Date:** {date.today().isoformat()}",
        f"**Purpose:** Validate that features_daily values match independently recomputed indicator values from prices_daily",
        "",
        "---",
        "",
        "## Executive Summary",
        "",
    ]
    
    # Count statuses
    pass_count = sum(1 for r in results.values() if r.status == ValidationStatus.PASS)
    warn_count = sum(1 for r in results.values() if r.status == ValidationStatus.WARN)
    fail_count = sum(1 for r in results.values() if r.status == ValidationStatus.FAIL)
    
    report_lines.extend([
        f"- **PASS:** {pass_count} indicators",
        f"- **WARN:** {warn_count} indicators",
        f"- **FAIL:** {fail_count} indicators",
        "",
        "## Indicator-by-Indicator Results",
        "",
    ])
    
    # Sort by status (FAIL first, then WARN, then PASS)
    sorted_results = sorted(
        results.items(),
        key=lambda x: (x[1].status.value == 'FAIL', x[1].status.value == 'WARN', x[1].status.value == 'PASS'),
        reverse=True,
    )
    
    for indicator_name, result in sorted_results:
        report_lines.extend([
            f"### {indicator_name}",
            "",
            f"- **Status:** {result.status.value}",
            f"- **Sample Count:** {result.sample_count}",
            f"- **Mean Absolute Error:** {result.mean_absolute_error:.6f}",
            f"- **Max Absolute Error:** {result.max_absolute_error:.6f}",
            f"- **Match Percentage:** {result.match_percentage:.2f}%",
            f"- **Tolerance:** {result.tolerance:.2%}",
        ])
        
        if result.mismatches:
            report_lines.extend([
                "",
                f"**Mismatches ({len(result.mismatches)}):**",
                "",
                "| Symbol | Date | Computed | Stored | Error |",
                "|--------|------|----------|--------|-------|",
            ])
            
            for symbol, mismatch_date, computed, stored in result.mismatches[:10]:  # Show first 10
                if stored is not None:
                    error = abs(computed - stored) / abs(stored) if abs(stored) > 1e-10 else abs(computed - stored)
                    report_lines.append(
                        f"| {symbol} | {mismatch_date.isoformat()} | {computed:.4f} | {stored:.4f} | {error:.4f} |"
                    )
                else:
                    report_lines.append(
                        f"| {symbol} | {mismatch_date.isoformat()} | {computed:.4f} | NULL | N/A |"
                    )
            
            if len(result.mismatches) > 10:
                report_lines.append(f"| ... | ... | ... | ... | ... | ({len(result.mismatches) - 10} more) |")
        
        report_lines.append("")
    
    # Mismatch summary
    report_lines.extend([
        "---",
        "",
        "## Mismatch Summary",
        "",
    ])
    
    all_mismatches = []
    for result in results.values():
        for symbol, mismatch_date, computed, stored in result.mismatches:
            all_mismatches.append((result.indicator_name, symbol, mismatch_date))
    
    if all_mismatches:
        report_lines.append(f"**Total Mismatches:** {len(all_mismatches)}")
        report_lines.append("")
        
        # Symbols affected
        symbols_affected = set(m[1] for m in all_mismatches)
        report_lines.append(f"**Symbols Affected ({len(symbols_affected)}):**")
        for symbol in sorted(symbols_affected):
            count = sum(1 for m in all_mismatches if m[1] == symbol)
            report_lines.append(f"- {symbol}: {count} mismatches")
        
        report_lines.append("")
        
        # Dates affected
        dates_affected = set(m[2] for m in all_mismatches)
        report_lines.append(f"**Dates Affected ({len(dates_affected)}):**")
        for d in sorted(dates_affected):
            count = sum(1 for m in all_mismatches if m[2] == d)
            report_lines.append(f"- {d.isoformat()}: {count} mismatches")
    else:
        report_lines.append("**No mismatches detected.**")
    
    report_lines.extend([
        "",
        "---",
        "",
        "## Overall Verdict",
        "",
    ])
    
    if fail_count > 0:
        verdict = "FAIL"
        explanation = f"{fail_count} indicator(s) failed validation with material deviations."
    elif warn_count > 0:
        verdict = "WARN"
        explanation = f"{warn_count} indicator(s) have small deviations but passed basic validation."
    else:
        verdict = "PASS"
        explanation = "All indicators passed validation within tolerance thresholds."
    
    report_lines.extend([
        f"**Verdict:** {verdict}",
        "",
        explanation,
        "",
        "---",
        "",
        "## Methodology",
        "",
        "1. Selected 10 liquid NSE symbols based on recent trading activity.",
        "2. Selected 5 dates per symbol from the most recent 6 months.",
        "3. Loaded raw OHLCV data from prices_daily.",
        "4. Independently recomputed indicators using standard formulas.",
        "5. Compared against stored values in features_daily.",
        "",
        "## Tolerance Thresholds",
        "",
        f"- **PASS:** Match percentage >= 95% (tolerance: {FeatureValidator.TOLERANCE_PASS:.1%})",
        f"- **WARN:** Match percentage >= 80% (tolerance: {FeatureValidator.TOLERANCE_WARN:.1%})",
        "- **FAIL:** Match percentage < 80%",
        "",
        "## Recommendations",
        "",
    ])
    
    if fail_count > 0:
        report_lines.extend([
            "1. **Investigate Failed Indicators:** Review calculation logic for indicators that failed validation.",
            "2. **Check Data Quality:** Verify price data quality for affected symbols and dates.",
            "3. **Recompute Features:** If calculation errors found, recompute features_daily for affected period.",
            "4. **Re-run Validation:** After fixes, re-run validation to confirm corrections.",
        ])
    elif warn_count > 0:
        report_lines.extend([
            "1. **Monitor Warned Indicators:** Small deviations may be acceptable but should be monitored.",
            "2. **Investigate Outliers:** Review specific mismatches to understand root cause.",
            "3. **Consider Tightening Tolerance:** If deviations are systematic, consider tightening tolerance thresholds.",
        ])
    else:
        report_lines.extend([
            "1. **No Action Required:** All indicators validated successfully.",
            "2. **Continue Monitoring:** Schedule periodic validation to catch future calculation errors.",
        ])
    
    report_lines.extend([
        "",
        "---",
        "",
        f"**Report Generated:** {date.today().isoformat()}",
        f"**Validation Script:** scripts/run_feature_validation.py",
    ])
    
    # Write report
    report_path = "docs/FEATURE_VALIDATION_REPORT.md"
    with open(report_path, "w") as f:
        f.write("\n".join(report_lines))
    
    print(f"Report written to: {report_path}")


if __name__ == "__main__":
    raise SystemExit(main())
