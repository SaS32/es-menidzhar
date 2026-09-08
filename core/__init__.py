# ── ЕС Мениджър ──────────────────────────────────────────────────────────────
# Single source of truth for the version number. The UI footer, the PDF
# reports and the build script all read it from here — do not hard-code the
# version anywhere else.
__version__ = "2.3.0"

from .paths import RESOURCE_DIR, DATA_DIR, resource, data
from .database import init_db, get_connection, audit, backup_db
from .apartments import *
from .finance import (
    get_categories, add_category, delete_category,
    get_current_fee_settings, get_fee_settings_history, save_fee_settings,
    generate_monthly_fees, get_monthly_fees, get_monthly_fees_range, update_monthly_fee,
    record_advance_payment, get_advance_payments, get_apt_credit_balance,
    update_advance_payment, delete_advance_payment,
    apply_credit_to_fee, apply_credits_for_apartment, apply_credits_for_period,
    add_transaction, get_transactions, delete_transaction,
    get_period_summary, get_cash_summary, get_dashboard_data,
)
from .audit import get_audit_log
from .accounting import (
    calculate_apartment_fee,
    calculate_final_amount,
    calculate_credit_application,
    derive_fee_status,
    summarise_fees,
    compute_balance,
)
