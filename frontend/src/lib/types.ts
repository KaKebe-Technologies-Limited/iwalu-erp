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
