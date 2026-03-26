"use client";

import { useState, useMemo } from "react";
import { cn } from "@/lib/utils";
import { useProducts } from "@/lib/hooks/useProducts";
import { useDiscounts } from "@/lib/hooks/useDiscounts";
import { useMyCurrentShift } from "@/lib/hooks/useShifts";
import { useCheckout } from "@/lib/hooks/useSales";
import type { Product, CartItem, CheckoutRequest } from "@/lib/types";

const PAYMENT_METHODS = [
  { value: "cash", label: "Cash" },
  { value: "mobile_money", label: "Mobile Money" },
  { value: "card", label: "Card" },
  { value: "bank", label: "Bank Transfer" },
] as const;

export default function POSCheckoutPage() {
  const [search, setSearch] = useState("");
  const [cart, setCart] = useState<CartItem[]>([]);
  const [saleDiscountId, setSaleDiscountId] = useState<number | undefined>();
  const [payments, setPayments] = useState<CheckoutRequest["payments"]>([{ payment_method: "cash", amount: "", reference: "" }]);
  const [notes, setNotes] = useState("");
  const [showReceipt, setShowReceipt] = useState(false);
  const [lastSale, setLastSale] = useState<any>(null);

  const { data: productsData } = useProducts({ search, is_active: "true" });
  const { data: discountsData } = useDiscounts({ is_active: "true" });
  const { data: currentShift } = useMyCurrentShift();
  const checkout = useCheckout();

  const activeDiscounts = discountsData?.results || [];

  // Cart calculations
  const cartTotals = useMemo(() => {
    let subtotal = 0;
    let taxTotal = 0;
    let discountTotal = 0;

    cart.forEach((item) => {
      const linePrice = Number(item.product.selling_price) * item.quantity;
      const lineTax = linePrice * (Number(item.product.tax_rate) / 100);
      let lineDiscount = 0;

      if (item.discount_id) {
        const disc = activeDiscounts.find((d) => d.id === item.discount_id);
        if (disc) {
          lineDiscount = disc.discount_type === "percentage"
            ? linePrice * (Number(disc.value) / 100)
            : Number(disc.value);
        }
      }

      subtotal += linePrice;
      taxTotal += lineTax;
      discountTotal += lineDiscount;
    });

    // Sale-level discount
    if (saleDiscountId) {
      const disc = activeDiscounts.find((d) => d.id === saleDiscountId);
      if (disc) {
        discountTotal += disc.discount_type === "percentage"
          ? subtotal * (Number(disc.value) / 100)
          : Number(disc.value);
      }
    }

    const grandTotal = subtotal + taxTotal - discountTotal;
    return { subtotal, taxTotal, discountTotal, grandTotal: Math.max(0, grandTotal) };
  }, [cart, saleDiscountId, activeDiscounts]);

  const addToCart = (product: Product) => {
    setCart((prev) => {
      const existing = prev.find((c) => c.product.id === product.id);
      if (existing) {
        return prev.map((c) =>
          c.product.id === product.id ? { ...c, quantity: c.quantity + 1 } : c
        );
      }
      return [...prev, { product, quantity: 1 }];
    });
  };

  const updateQuantity = (productId: number, quantity: number) => {
    if (quantity <= 0) {
      setCart((prev) => prev.filter((c) => c.product.id !== productId));
    } else {
      setCart((prev) => prev.map((c) => c.product.id === productId ? { ...c, quantity } : c));
    }
  };

  const setItemDiscount = (productId: number, discountId: number | undefined) => {
    setCart((prev) => prev.map((c) => c.product.id === productId ? { ...c, discount_id: discountId } : c));
  };

  const addPaymentLine = () => {
    setPayments([...payments, { payment_method: "cash", amount: "", reference: "" }]);
  };

  const updatePayment = (index: number, field: string, value: string) => {
    setPayments(payments.map((p, i) => i === index ? { ...p, [field]: value } : p));
  };

  const removePayment = (index: number) => {
    if (payments.length > 1) setPayments(payments.filter((_, i) => i !== index));
  };

  const totalPaid = payments.reduce((sum, p) => sum + (Number(p.amount) || 0), 0);
  const changeDue = totalPaid - cartTotals.grandTotal;

  const handleCheckout = async () => {
    if (!currentShift) return alert("You must have an open shift to process a sale.");
    if (cart.length === 0) return alert("Cart is empty.");
    if (totalPaid < cartTotals.grandTotal) return alert("Insufficient payment amount.");

    const payload: CheckoutRequest = {
      items: cart.map((c) => ({
        product_id: c.product.id,
        quantity: c.quantity.toFixed(3),
        ...(c.discount_id ? { discount_id: c.discount_id } : {}),
      })),
      payments: payments.filter((p) => Number(p.amount) > 0).map((p) => ({
        payment_method: p.payment_method,
        amount: Number(p.amount).toFixed(2),
        ...(p.reference ? { reference: p.reference } : {}),
      })),
      ...(saleDiscountId ? { discount_id: saleDiscountId } : {}),
      ...(notes ? { notes } : {}),
    };

    try {
      const result = await checkout.mutateAsync(payload);
      setLastSale(result);
      setShowReceipt(true);
      setCart([]);
      setPayments([{ payment_method: "cash", amount: "", reference: "" }]);
      setSaleDiscountId(undefined);
      setNotes("");
    } catch {
      // Error handled by mutation
    }
  };

  // No shift warning
  if (!currentShift) {
    return (
      <div className="max-w-lg mx-auto mt-20 text-center space-y-4">
        <div className="w-16 h-16 bg-amber-50 rounded-2xl flex items-center justify-center mx-auto">
          <svg className="w-8 h-8 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
          </svg>
        </div>
        <h2 className="text-xl font-bold text-gray-900">No Active Shift</h2>
        <p className="text-gray-500">You need to open a shift before processing sales. Go to the Shifts page to open one.</p>
        <a href="/dashboard/shifts" className="inline-block px-5 py-2.5 rounded-xl bg-black text-white text-sm font-semibold hover:bg-zinc-800">
          Go to Shifts
        </a>
      </div>
    );
  }

  return (
    <div className="h-[calc(100vh-6rem)] flex flex-col lg:flex-row gap-4">
      {/* Left: Product search & grid */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Search */}
        <div className="flex items-center gap-2 bg-white border border-gray-200 rounded-xl px-3 py-2 mb-4">
          <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            placeholder="Search products by name, SKU, or barcode..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="bg-transparent text-sm outline-none placeholder-gray-400 w-full"
            autoFocus
          />
        </div>

        {/* Product Grid */}
        <div className="flex-1 overflow-y-auto">
          <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-4 gap-3">
            {productsData?.results.map((product) => (
              <button
                key={product.id}
                onClick={() => addToCart(product)}
                className="bg-white border border-gray-100 rounded-xl p-3 text-left hover:border-black hover:shadow-md transition-all group"
              >
                <p className="text-sm font-semibold text-gray-900 truncate group-hover:text-black">{product.name}</p>
                <p className="text-xs text-gray-400 mt-0.5">{product.sku}</p>
                <div className="flex items-center justify-between mt-2">
                  <p className="text-sm font-bold text-gray-900">UGX {Number(product.selling_price).toLocaleString()}</p>
                  {product.track_stock && (
                    <span className={cn("text-xs font-medium", product.is_low_stock ? "text-red-500" : "text-gray-400")}>
                      {product.stock_quantity} left
                    </span>
                  )}
                </div>
              </button>
            ))}
          </div>
          {productsData && productsData.results.length === 0 && (
            <div className="text-center text-gray-400 py-12 text-sm">No products found</div>
          )}
        </div>
      </div>

      {/* Right: Cart */}
      <div className="w-full lg:w-[400px] bg-white border border-gray-200 rounded-2xl flex flex-col shadow-sm">
        {/* Cart Header */}
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="text-lg font-bold text-gray-900">Cart</h2>
          <span className="text-xs text-gray-400">{cart.length} items</span>
        </div>

        {/* Cart Items */}
        <div className="flex-1 overflow-y-auto px-5 py-3 space-y-3">
          {cart.length === 0 ? (
            <div className="text-center text-gray-400 py-8 text-sm">Add products to start a sale</div>
          ) : (
            cart.map((item) => (
              <div key={item.product.id} className="border border-gray-100 rounded-xl p-3">
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-gray-900 truncate">{item.product.name}</p>
                    <p className="text-xs text-gray-400">UGX {Number(item.product.selling_price).toLocaleString()} each</p>
                  </div>
                  <p className="text-sm font-bold text-gray-900 ml-2">
                    UGX {(Number(item.product.selling_price) * item.quantity).toLocaleString()}
                  </p>
                </div>
                <div className="flex items-center justify-between mt-2">
                  <div className="flex items-center gap-2">
                    <button onClick={() => updateQuantity(item.product.id, item.quantity - 1)} className="w-7 h-7 rounded-lg bg-gray-100 flex items-center justify-center text-gray-600 hover:bg-gray-200 text-sm font-bold">-</button>
                    <span className="text-sm font-semibold w-8 text-center">{item.quantity}</span>
                    <button onClick={() => updateQuantity(item.product.id, item.quantity + 1)} className="w-7 h-7 rounded-lg bg-gray-100 flex items-center justify-center text-gray-600 hover:bg-gray-200 text-sm font-bold">+</button>
                  </div>
                  {activeDiscounts.length > 0 && (
                    <select
                      value={item.discount_id || ""}
                      onChange={(e) => setItemDiscount(item.product.id, e.target.value ? Number(e.target.value) : undefined)}
                      className="text-xs border border-gray-200 rounded-lg px-2 py-1 text-gray-600"
                    >
                      <option value="">No discount</option>
                      {activeDiscounts.map((d) => (
                        <option key={d.id} value={d.id}>
                          {d.name} ({d.discount_type === "percentage" ? `${d.value}%` : `UGX ${Number(d.value).toLocaleString()}`})
                        </option>
                      ))}
                    </select>
                  )}
                </div>
              </div>
            ))
          )}
        </div>

        {/* Cart Footer */}
        {cart.length > 0 && (
          <div className="border-t border-gray-100 px-5 py-4 space-y-3">
            {/* Sale-level discount */}
            {activeDiscounts.length > 0 && (
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Sale Discount</label>
                <select
                  value={saleDiscountId || ""}
                  onChange={(e) => setSaleDiscountId(e.target.value ? Number(e.target.value) : undefined)}
                  className="w-full text-xs border border-gray-200 rounded-lg px-2 py-1.5 text-gray-600"
                >
                  <option value="">None</option>
                  {activeDiscounts.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name} ({d.discount_type === "percentage" ? `${d.value}%` : `UGX ${Number(d.value).toLocaleString()}`})
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Totals */}
            <div className="space-y-1 text-sm">
              <div className="flex justify-between"><span className="text-gray-500">Subtotal</span><span>UGX {cartTotals.subtotal.toLocaleString()}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Tax</span><span>UGX {cartTotals.taxTotal.toLocaleString()}</span></div>
              {cartTotals.discountTotal > 0 && (
                <div className="flex justify-between"><span className="text-gray-500">Discount</span><span className="text-red-600">-UGX {cartTotals.discountTotal.toLocaleString()}</span></div>
              )}
              <div className="flex justify-between font-bold text-base pt-1 border-t border-gray-100">
                <span>Total</span>
                <span>UGX {cartTotals.grandTotal.toLocaleString()}</span>
              </div>
            </div>

            {/* Payments */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-xs font-medium text-gray-500">Payments</label>
                <button onClick={addPaymentLine} className="text-xs text-blue-600 hover:text-blue-800 font-medium">+ Split</button>
              </div>
              <div className="space-y-2">
                {payments.map((p, i) => (
                  <div key={i} className="flex gap-2">
                    <select
                      value={p.payment_method}
                      onChange={(e) => updatePayment(i, "payment_method", e.target.value)}
                      className="text-xs border border-gray-200 rounded-lg px-2 py-1.5 w-28"
                    >
                      {PAYMENT_METHODS.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
                    </select>
                    <input
                      type="number"
                      placeholder="Amount"
                      value={p.amount}
                      onChange={(e) => updatePayment(i, "amount", e.target.value)}
                      className="flex-1 text-xs border border-gray-200 rounded-lg px-2 py-1.5"
                    />
                    {p.payment_method !== "cash" && (
                      <input
                        type="text"
                        placeholder="Ref"
                        value={p.reference || ""}
                        onChange={(e) => updatePayment(i, "reference", e.target.value)}
                        className="w-20 text-xs border border-gray-200 rounded-lg px-2 py-1.5"
                      />
                    )}
                    {payments.length > 1 && (
                      <button onClick={() => removePayment(i)} className="text-red-400 hover:text-red-600 text-xs px-1">X</button>
                    )}
                  </div>
                ))}
              </div>
              {changeDue > 0 && (
                <p className="text-xs text-emerald-600 font-semibold mt-1">Change: UGX {changeDue.toLocaleString()}</p>
              )}
              {totalPaid > 0 && totalPaid < cartTotals.grandTotal && (
                <p className="text-xs text-red-500 font-semibold mt-1">Remaining: UGX {(cartTotals.grandTotal - totalPaid).toLocaleString()}</p>
              )}
            </div>

            {/* Notes */}
            <input
              type="text"
              placeholder="Notes (optional)"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="w-full text-xs border border-gray-200 rounded-lg px-3 py-2 text-gray-600"
            />

            {/* Checkout Button */}
            <button
              onClick={handleCheckout}
              disabled={checkout.isPending || cart.length === 0 || totalPaid < cartTotals.grandTotal}
              className="w-full py-3 rounded-xl bg-black text-white font-bold text-sm hover:bg-zinc-800 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            >
              {checkout.isPending ? "Processing..." : `Checkout - UGX ${cartTotals.grandTotal.toLocaleString()}`}
            </button>

            {checkout.isError && (
              <p className="text-xs text-red-500 text-center">Checkout failed. Please try again.</p>
            )}
          </div>
        )}
      </div>

      {/* Receipt Modal */}
      {showReceipt && lastSale && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={() => setShowReceipt(false)}>
          <div className="bg-white rounded-2xl p-6 w-full max-w-sm shadow-xl" onClick={(e) => e.stopPropagation()}>
            <div className="text-center mb-4">
              <div className="w-12 h-12 bg-emerald-50 rounded-full flex items-center justify-center mx-auto mb-3">
                <svg className="w-6 h-6 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <h2 className="text-lg font-bold text-gray-900">Sale Complete</h2>
              <p className="text-sm text-gray-500">Receipt #{lastSale.receipt_number}</p>
            </div>
            <div className="bg-gray-50 rounded-xl p-4 mb-4">
              <div className="flex justify-between text-sm font-bold">
                <span>Total</span>
                <span>UGX {Number(lastSale.grand_total).toLocaleString()}</span>
              </div>
            </div>
            <button onClick={() => setShowReceipt(false)} className="w-full py-2.5 rounded-xl bg-black text-white text-sm font-semibold hover:bg-zinc-800">
              New Sale
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
