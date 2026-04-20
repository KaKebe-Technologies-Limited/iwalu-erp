// Pagination
export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

// Auth
export interface User {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  role: 'admin' | 'manager' | 'cashier' | 'attendant' | 'accountant';
  is_active: boolean;
  created_at: string;
}

// Outlets
export interface Outlet {
  id: number;
  name: string;
  outlet_type: 'fuel_station' | 'cafe' | 'supermarket' | 'boutique' | 'bridal' | 'general';
  address: string;
  phone: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// Categories
export interface Category {
  id: number;
  name: string;
  business_unit: 'fuel' | 'cafe' | 'supermarket' | 'boutique' | 'bridal' | 'general';
  description: string;
  parent: number | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// Products
export interface Product {
  id: number;
  name: string;
  sku: string;
  barcode: string;
  category: number;
  category_name: string;
  cost_price: string;
  selling_price: string;
  tax_rate: string;
  track_stock: boolean;
  stock_quantity: string;
  reorder_level: string;
  unit: 'piece' | 'litre' | 'kg' | 'metre' | 'box' | 'pack';
  is_active: boolean;
  is_low_stock: boolean;
  created_at: string;
  updated_at: string;
}

// Discounts
export interface Discount {
  id: number;
  name: string;
  discount_type: 'percentage' | 'fixed';
  value: string;
  is_active: boolean;
  valid_from: string | null;
  valid_until: string | null;
  created_at: string;
  updated_at: string;
}

// Shifts
export interface Shift {
  id: number;
  outlet: number;
  user_id: number;
  status: 'open' | 'closed';
  opening_cash: string;
  closing_cash: string | null;
  expected_cash: string | null;
  notes: string;
  opened_at: string;
  closed_at: string | null;
}

// Sales
export interface Sale {
  id: number;
  receipt_number: string;
  outlet: number;
  shift: number;
  cashier_id: number;
  subtotal: string;
  tax_total: string;
  discount_total: string;
  grand_total: string;
  discount: number | null;
  status: 'completed' | 'voided' | 'refunded';
  notes: string;
  items: SaleItem[];
  payments: SalePayment[];
  created_at: string;
  updated_at: string;
}

export interface SaleItem {
  id: number;
  product: number;
  product_name: string;
  unit_price: string;
  quantity: string;
  tax_rate: string;
  tax_amount: string;
  discount: number | null;
  discount_amount: string;
  line_total: string;
}

export interface SalePayment {
  id: number;
  payment_method: 'cash' | 'bank' | 'mobile_money' | 'card';
  amount: string;
  reference: string;
  created_at: string;
}

// Checkout
export interface CheckoutRequest {
  items: Array<{
    product_id: number;
    quantity: string;
    discount_id?: number;
  }>;
  payments: Array<{
    payment_method: 'cash' | 'bank' | 'mobile_money' | 'card';
    amount: string;
    reference?: string;
  }>;
  discount_id?: number;
  notes?: string;
}

// Cart (frontend-only)
export interface CartItem {
  product: Product;
  quantity: number;
  discount_id?: number;
}

// ── Inventory ────────────────────────────────────────────────────────────────

export interface Supplier {
  id: number;
  name: string;
  contact_person: string;
  email: string;
  phone: string;
  address: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface OutletStock {
  id: number;
  outlet: number;
  outlet_name: string;
  product: number;
  product_name: string;
  product_sku: string;
  quantity: string;
  updated_at: string;
}

export interface PurchaseOrderItem {
  id: number;
  product: number;
  product_name: string;
  quantity_ordered: string;
  quantity_received: string;
  unit_cost: string;
  line_total: string;
}

export interface PurchaseOrder {
  id: number;
  po_number: string;
  supplier: number;
  supplier_name: string;
  outlet: number;
  outlet_name: string;
  ordered_by: number;
  status: 'draft' | 'submitted' | 'partial' | 'received' | 'cancelled';
  expected_date: string | null;
  total_cost: string;
  notes: string;
  items: PurchaseOrderItem[];
  created_at: string;
  updated_at: string;
}

export interface StockTransferItem {
  id: number;
  product: number;
  product_name: string;
  quantity: string;
  quantity_received: string;
}

export interface StockTransfer {
  id: number;
  transfer_number: string;
  from_outlet: number;
  from_outlet_name: string;
  to_outlet: number;
  to_outlet_name: string;
  initiated_by: number;
  status: 'pending' | 'in_transit' | 'completed' | 'cancelled';
  notes: string;
  items: StockTransferItem[];
  created_at: string;
  updated_at: string;
}

export interface StockAuditLog {
  id: number;
  product: number;
  product_name: string;
  outlet: number | null;
  outlet_name: string | null;
  movement_type: 'sale' | 'void' | 'adjustment' | 'transfer_out' | 'transfer_in' | 'purchase';
  movement_type_display: string;
  quantity_change: string;
  quantity_before: string;
  quantity_after: string;
  reference_type: string;
  reference_id: number | null;
  user_id: number | null;
  notes: string;
  created_at: string;
}

// ── Reports ──────────────────────────────────────────────────────────────────

export interface DashboardData {
  today_sales: number;
  today_revenue: string;
  active_shifts: number;
  low_stock_count: number;
  date: string;
}

export interface SalesSummary {
  total_sales: number;
  total_revenue: string;
  total_tax: string;
  total_discount: string;
  avg_sale: string;
  date_from: string;
  date_to: string;
}

export interface SalesByOutlet {
  outlet: number;
  outlet_name: string;
  total_sales: number;
  total_revenue: string;
}

export interface SalesByProduct {
  product: number;
  product_name: string;
  product_sku: string;
  total_quantity: string;
  total_revenue: string;
}

export interface SalesByPaymentMethod {
  payment_method: string;
  count: number;
  total_amount: string;
}

export interface HourlySales {
  hour: string;
  total_sales: number;
  total_revenue: string;
}

export interface StockLevel {
  id?: number;
  outlet?: number;
  product?: number;
  name?: string;
  sku?: string;
  stock_quantity?: string;
  quantity?: string;
  outlet_name?: string;
  product_name?: string;
  product_sku?: string;
  reorder_level: string;
  category_name?: string;
}

export interface StockMovementSummary {
  movement_type: string;
  count: number;
  total_quantity: string;
}

export interface ShiftSummaryEntry {
  id: number;
  outlet: number;
  outlet_name: string;
  user_id: number;
  opening_cash: string;
  closing_cash: string;
  expected_cash: string;
  opened_at: string;
  closed_at: string;
  total_sales: number;
  total_revenue: string;
}

// ── Finance ──────────────────────────────────────────────────────────────────

export interface Account {
  id: number;
  code: string;
  name: string;
  account_type: 'asset' | 'liability' | 'equity' | 'revenue' | 'expense';
  parent: number | null;
  parent_name: string | null;
  description: string;
  is_active: boolean;
  is_system: boolean;
  outlet: number | null;
  outlet_name: string | null;
  children_count: number;
  created_at: string;
  updated_at: string;
}

export interface FiscalPeriod {
  id: number;
  name: string;
  start_date: string;
  end_date: string;
  is_closed: boolean;
  closed_by: number | null;
  closed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface JournalEntryLine {
  id: number;
  account: number;
  account_code: string;
  account_name: string;
  description: string;
  debit: string;
  credit: string;
  outlet: number | null;
}

export interface JournalEntry {
  id: number;
  entry_number: string;
  date: string;
  fiscal_period: number;
  fiscal_period_name: string;
  description: string;
  source: string;
  reference_type: string;
  reference_id: number | null;
  status: 'draft' | 'posted' | 'voided';
  created_by: number;
  posted_by: number | null;
  posted_at: string | null;
  voided_by: number | null;
  voided_at: string | null;
  lines: JournalEntryLine[];
  created_at: string;
  updated_at: string;
}

export interface JournalEntryLineCreate {
  account_id: number;
  description?: string;
  debit: string;
  credit: string;
  outlet_id?: number | null;
}

export interface JournalEntryCreate {
  date: string;
  description: string;
  lines: JournalEntryLineCreate[];
}

export interface TrialBalanceLine {
  account_id: number;
  account_code: string;
  account_name: string;
  account_type: string;
  debit: string;
  credit: string;
  balance: string;
}

export interface ProfitLossLineItem {
  account_code: string;
  account_name: string;
  amount: string;
}

export interface ProfitLoss {
  date_from: string;
  date_to: string;
  revenue: ProfitLossLineItem[];
  total_revenue: string;
  expenses: ProfitLossLineItem[];
  total_expenses: string;
  net_income: string;
}

export interface BalanceSheetLine {
  account_code: string;
  account_name: string;
  balance: string;
}

export interface BalanceSheet {
  as_of_date: string;
  assets: BalanceSheetLine[];
  total_assets: string;
  liabilities: BalanceSheetLine[];
  total_liabilities: string;
  equity: BalanceSheetLine[];
  total_equity: string;
  total_liabilities_and_equity: string;
}

// ── HR ───────────────────────────────────────────────────────────────────────

export interface Department {
  id: number;
  name: string;
  description: string;
  outlet: number | null;
  outlet_name: string | null;
  is_active: boolean;
  employee_count: number;
  created_at: string;
  updated_at: string;
}

export interface Employee {
  id: number;
  user_id: number;
  employee_number: string;
  department: number | null;
  department_name: string | null;
  outlet: number | null;
  outlet_name: string | null;
  designation: string;
  employment_type: 'full_time' | 'part_time' | 'contract';
  employment_status: 'active' | 'terminated' | 'suspended';
  date_hired: string;
  date_terminated: string | null;
  basic_salary: string;
  bank_name: string;
  bank_account: string;
  mobile_money_number: string;
  nssf_number: string;
  tin_number: string;
  emergency_contact_name: string;
  emergency_contact_phone: string;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface LeaveType {
  id: number;
  name: string;
  days_per_year: number;
  is_paid: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface LeaveBalance {
  id: number;
  employee: number;
  employee_number: string;
  leave_type: number;
  leave_type_name: string;
  year: number;
  entitled_days: string;
  used_days: string;
  carried_over: string;
  remaining_days: string;
}

export interface LeaveRequest {
  id: number;
  employee: number;
  employee_number: string;
  leave_type: number;
  leave_type_name: string;
  start_date: string;
  end_date: string;
  days_requested: string;
  reason: string;
  status: 'pending' | 'approved' | 'rejected' | 'cancelled';
  approved_by: number | null;
  approved_at: string | null;
  rejection_reason: string;
  created_at: string;
  updated_at: string;
}

export interface Attendance {
  id: number;
  employee: number;
  employee_number: string;
  date: string;
  clock_in: string | null;
  clock_out: string | null;
  outlet: number | null;
  hours_worked: number;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface PaySlipLine {
  id: number;
  line_type: string;
  description: string;
  amount: string;
}

export interface PaySlip {
  id: number;
  payroll_period: number;
  employee: number;
  employee_number: string;
  basic_salary: string;
  gross_pay: string;
  total_deductions: string;
  net_pay: string;
  lines: PaySlipLine[];
  created_at: string;
}

export interface PayrollPeriod {
  id: number;
  name: string;
  start_date: string;
  end_date: string;
  status: 'draft' | 'processing' | 'approved' | 'paid';
  processed_by: number | null;
  approved_by: number | null;
  journal_entry: number | null;
  total_gross: string;
  total_deductions: string;
  total_net: string;
  pay_slips_count: number;
  created_at: string;
  updated_at: string;
}

// ── Fuel Station ─────────────────────────────────────────────────────────────

export interface Pump {
  id: number;
  outlet: number;
  outlet_name: string;
  product: number;
  product_name: string;
  pump_number: number;
  name: string;
  status: 'active' | 'inactive' | 'maintenance';
  status_display: string;
  created_at: string;
  updated_at: string;
}

export interface Tank {
  id: number;
  outlet: number;
  outlet_name: string;
  product: number;
  product_name: string;
  name: string;
  capacity: string;
  current_level: string;
  reorder_level: string;
  is_active: boolean;
  fill_percentage: number;
  is_low: boolean;
  created_at: string;
  updated_at: string;
}

export interface TankReading {
  id: number;
  tank: number;
  tank_name: string;
  reading_level: string;
  reading_type: 'manual' | 'automatic' | 'delivery' | 'reconciliation';
  reading_type_display: string;
  recorded_by: number;
  notes: string;
  reading_at: string;
  created_at: string;
  updated_at: string;
}

export interface PumpReading {
  id: number;
  pump: number;
  pump_number: number;
  pump_name: string;
  shift: number;
  opening_reading: string;
  closing_reading: string | null;
  volume_dispensed: string | null;
  recorded_by: number;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface FuelDelivery {
  id: number;
  tank: number;
  tank_name: string;
  supplier: number;
  supplier_name: string;
  delivery_date: string;
  volume_ordered: string | null;
  volume_received: string;
  unit_cost: string;
  total_cost: string;
  delivery_note_number: string;
  tank_level_before: string;
  tank_level_after: string;
  received_by: number;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface FuelReconciliation {
  id: number;
  date: string;
  outlet: number;
  outlet_name: string;
  tank: number;
  tank_name: string;
  opening_stock: string;
  closing_stock: string;
  total_received: string;
  total_dispensed: string;
  expected_closing: string;
  variance: string;
  variance_percentage: string;
  variance_type: 'gain' | 'loss' | 'within_tolerance';
  variance_type_display: string;
  status: 'draft' | 'confirmed';
  notes: string;
  reconciled_by: number;
  created_at: string;
  updated_at: string;
}

export interface DailyPumpReportEntry {
  pump_number: number;
  pump_name: string;
  product: string;
  outlet: string;
  shift_id: number;
  opening_reading: string;
  closing_reading: string | null;
  volume_dispensed: string | null;
  recorded_by: number;
}

export interface DailyPumpProductTotal {
  "pump__product__name": string;
  total_volume: string | null;
}

export interface DailyPumpReport {
  date: string;
  pumps: DailyPumpReportEntry[];
  totals_by_product: DailyPumpProductTotal[];
}

export interface VarianceReportSummary {
  total_variance: string | null;
  loss_count: number;
  gain_count: number;
  within_tolerance_count: number;
}

export interface VarianceReport {
  date_from: string;
  date_to: string;
  reconciliations: FuelReconciliation[];
  summary: VarianceReportSummary;
}
