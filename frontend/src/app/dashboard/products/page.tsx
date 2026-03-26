"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { useProducts, useCreateProduct, useUpdateProduct, useAdjustStock } from "@/lib/hooks/useProducts";
import { useCategories, useCreateCategory } from "@/lib/hooks/useCategories";
import type { Product, Category } from "@/lib/types";

const BUSINESS_UNITS = [
  { value: "", label: "All Units" },
  { value: "fuel", label: "Fuel" },
  { value: "cafe", label: "Cafe" },
  { value: "supermarket", label: "Supermarket" },
  { value: "boutique", label: "Boutique" },
  { value: "bridal", label: "Bridal" },
  { value: "general", label: "General" },
];

const UNITS = ["piece", "litre", "kg", "metre", "box", "pack"] as const;

export default function ProductsPage() {
  const [tab, setTab] = useState<"products" | "categories">("products");
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [unitFilter, setUnitFilter] = useState("");
  const [page, setPage] = useState(1);

  // Products
  const { data: productsData, isLoading: productsLoading } = useProducts({ search, category: categoryFilter, page });
  const createProduct = useCreateProduct();
  const updateProduct = useUpdateProduct();
  const adjustStock = useAdjustStock();

  // Categories
  const { data: categoriesData, isLoading: categoriesLoading } = useCategories({ business_unit: unitFilter, page });
  const createCategory = useCreateCategory();

  const [showProductModal, setShowProductModal] = useState(false);
  const [showCategoryModal, setShowCategoryModal] = useState(false);
  const [showStockModal, setShowStockModal] = useState(false);
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);
  const [stockTarget, setStockTarget] = useState<Product | null>(null);

  const [productForm, setProductForm] = useState({
    name: "", sku: "", barcode: "", category: "", cost_price: "", selling_price: "", tax_rate: "0", unit: "piece" as Product["unit"], track_stock: true, reorder_level: "10",
  });
  const [categoryForm, setCategoryForm] = useState({ name: "", business_unit: "general" as Category["business_unit"], description: "" });
  const [stockForm, setStockForm] = useState({ quantity: "", reason: "" });

  const openCreateProduct = () => {
    setEditingProduct(null);
    setProductForm({ name: "", sku: "", barcode: "", category: "", cost_price: "", selling_price: "", tax_rate: "0", unit: "piece", track_stock: true, reorder_level: "10" });
    setShowProductModal(true);
  };

  const openEditProduct = (p: Product) => {
    setEditingProduct(p);
    setProductForm({
      name: p.name, sku: p.sku, barcode: p.barcode, category: String(p.category), cost_price: p.cost_price, selling_price: p.selling_price,
      tax_rate: p.tax_rate, unit: p.unit, track_stock: p.track_stock, reorder_level: p.reorder_level,
    });
    setShowProductModal(true);
  };

  const handleProductSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const payload = { ...productForm, category: Number(productForm.category) };
    if (editingProduct) {
      await updateProduct.mutateAsync({ id: editingProduct.id, ...payload });
    } else {
      await createProduct.mutateAsync(payload);
    }
    setShowProductModal(false);
  };

  const handleCategorySubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await createCategory.mutateAsync(categoryForm);
    setShowCategoryModal(false);
  };

  const handleStockSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (stockTarget) {
      await adjustStock.mutateAsync({ id: stockTarget.id, ...stockForm });
      setShowStockModal(false);
    }
  };

  const productPages = productsData ? Math.ceil(productsData.count / 20) : 0;
  const categoryPages = categoriesData ? Math.ceil(categoriesData.count / 20) : 0;

  return (
    <div className="space-y-6 max-w-[1400px]">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-gray-900 tracking-tight">Products & Categories</h1>
          <p className="text-sm text-gray-500 mt-1">Manage your product catalog and categories</p>
        </div>
        <button
          onClick={tab === "products" ? openCreateProduct : () => { setCategoryForm({ name: "", business_unit: "general", description: "" }); setShowCategoryModal(true); }}
          className="px-4 py-2.5 rounded-xl bg-black text-white text-sm font-semibold hover:bg-zinc-800 transition-all shadow-sm"
        >
          + New {tab === "products" ? "Product" : "Category"}
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-100 rounded-xl p-1 w-fit">
        {(["products", "categories"] as const).map((t) => (
          <button key={t} onClick={() => { setTab(t); setPage(1); }} className={cn(
            "px-4 py-2 rounded-lg text-sm font-medium transition-all capitalize",
            tab === t ? "bg-white shadow-sm text-gray-900" : "text-gray-500 hover:text-gray-700"
          )}>{t}</button>
        ))}
      </div>

      {tab === "products" ? (
        <>
          {/* Product Filters */}
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="flex items-center gap-2 bg-white border border-gray-200 rounded-xl px-3 py-2 flex-1">
              <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <input type="text" placeholder="Search by name, SKU, or barcode..." value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} className="bg-transparent text-sm outline-none placeholder-gray-400 w-full" />
            </div>
          </div>

          {/* Products Table */}
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
            {productsLoading ? (
              <div className="p-12 text-center text-gray-400">Loading products...</div>
            ) : !productsData?.results.length ? (
              <div className="p-12 text-center text-gray-400">No products found</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50">
                      <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Product</th>
                      <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">SKU</th>
                      <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Category</th>
                      <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Price</th>
                      <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Stock</th>
                      <th className="text-center px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Status</th>
                      <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {productsData.results.map((product) => (
                      <tr key={product.id} className="hover:bg-gray-50/50 transition-colors">
                        <td className="px-6 py-3">
                          <p className="font-medium text-gray-900">{product.name}</p>
                          <p className="text-xs text-gray-400">{product.unit}</p>
                        </td>
                        <td className="px-6 py-3 text-gray-600 font-mono text-xs">{product.sku}</td>
                        <td className="px-6 py-3 text-gray-600">{product.category_name}</td>
                        <td className="px-6 py-3 text-right font-bold text-gray-900">UGX {Number(product.selling_price).toLocaleString()}</td>
                        <td className="px-6 py-3 text-right">
                          <span className={cn("font-semibold", product.is_low_stock ? "text-red-600" : "text-gray-900")}>
                            {product.stock_quantity}
                          </span>
                          {product.is_low_stock && <span className="ml-1 text-xs text-red-500">Low</span>}
                        </td>
                        <td className="px-6 py-3 text-center">
                          <span className={cn("px-2.5 py-1 rounded-full text-xs font-semibold", product.is_active ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700")}>
                            {product.is_active ? "Active" : "Inactive"}
                          </span>
                        </td>
                        <td className="px-6 py-3 text-right space-x-2">
                          <button onClick={() => openEditProduct(product)} className="text-gray-400 hover:text-gray-700 text-xs font-medium">Edit</button>
                          <button onClick={() => { setStockTarget(product); setStockForm({ quantity: "", reason: "" }); setShowStockModal(true); }} className="text-blue-500 hover:text-blue-700 text-xs font-medium">Adjust Stock</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {productPages > 1 && (
              <div className="px-6 py-3 border-t border-gray-100 flex items-center justify-between">
                <p className="text-xs text-gray-500">{productsData?.count} products total</p>
                <div className="flex gap-1">
                  <button disabled={page <= 1} onClick={() => setPage(page - 1)} className="px-3 py-1 rounded-lg text-xs font-medium bg-gray-100 text-gray-600 disabled:opacity-40">Prev</button>
                  <span className="px-3 py-1 text-xs text-gray-500">Page {page} of {productPages}</span>
                  <button disabled={page >= productPages} onClick={() => setPage(page + 1)} className="px-3 py-1 rounded-lg text-xs font-medium bg-gray-100 text-gray-600 disabled:opacity-40">Next</button>
                </div>
              </div>
            )}
          </div>
        </>
      ) : (
        <>
          {/* Category Filters */}
          <div className="flex flex-col sm:flex-row gap-3">
            <select value={unitFilter} onChange={(e) => { setUnitFilter(e.target.value); setPage(1); }} className="bg-white border border-gray-200 rounded-xl px-3 py-2 text-sm text-gray-700">
              {BUSINESS_UNITS.map((u) => (
                <option key={u.value} value={u.value}>{u.label}</option>
              ))}
            </select>
          </div>

          {/* Categories Table */}
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
            {categoriesLoading ? (
              <div className="p-12 text-center text-gray-400">Loading categories...</div>
            ) : !categoriesData?.results.length ? (
              <div className="p-12 text-center text-gray-400">No categories found</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50">
                      <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Name</th>
                      <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Business Unit</th>
                      <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Description</th>
                      <th className="text-center px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {categoriesData.results.map((cat) => (
                      <tr key={cat.id} className="hover:bg-gray-50/50 transition-colors">
                        <td className="px-6 py-3 font-medium text-gray-900">{cat.name}</td>
                        <td className="px-6 py-3">
                          <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-gray-100 text-gray-700 capitalize">{cat.business_unit}</span>
                        </td>
                        <td className="px-6 py-3 text-gray-600">{cat.description || "-"}</td>
                        <td className="px-6 py-3 text-center">
                          <span className={cn("px-2.5 py-1 rounded-full text-xs font-semibold", cat.is_active ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700")}>
                            {cat.is_active ? "Active" : "Inactive"}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {categoryPages > 1 && (
              <div className="px-6 py-3 border-t border-gray-100 flex items-center justify-between">
                <p className="text-xs text-gray-500">{categoriesData?.count} categories total</p>
                <div className="flex gap-1">
                  <button disabled={page <= 1} onClick={() => setPage(page - 1)} className="px-3 py-1 rounded-lg text-xs font-medium bg-gray-100 text-gray-600 disabled:opacity-40">Prev</button>
                  <span className="px-3 py-1 text-xs text-gray-500">Page {page} of {categoryPages}</span>
                  <button disabled={page >= categoryPages} onClick={() => setPage(page + 1)} className="px-3 py-1 rounded-lg text-xs font-medium bg-gray-100 text-gray-600 disabled:opacity-40">Next</button>
                </div>
              </div>
            )}
          </div>
        </>
      )}

      {/* Product Modal */}
      {showProductModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={() => setShowProductModal(false)}>
          <div className="bg-white rounded-2xl p-6 w-full max-w-lg shadow-xl max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-bold text-gray-900 mb-4">{editingProduct ? "Edit Product" : "New Product"}</h2>
            <form onSubmit={handleProductSubmit} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
                  <input value={productForm.name} onChange={(e) => setProductForm({ ...productForm, name: e.target.value })} required className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-black/10" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">SKU</label>
                  <input value={productForm.sku} onChange={(e) => setProductForm({ ...productForm, sku: e.target.value })} required className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-black/10" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Cost Price</label>
                  <input type="number" step="0.01" value={productForm.cost_price} onChange={(e) => setProductForm({ ...productForm, cost_price: e.target.value })} required className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-black/10" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Selling Price</label>
                  <input type="number" step="0.01" value={productForm.selling_price} onChange={(e) => setProductForm({ ...productForm, selling_price: e.target.value })} required className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-black/10" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Unit</label>
                  <select value={productForm.unit} onChange={(e) => setProductForm({ ...productForm, unit: e.target.value as Product["unit"] })} className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm">
                    {UNITS.map((u) => <option key={u} value={u} className="capitalize">{u}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Tax Rate (%)</label>
                  <input type="number" step="0.01" value={productForm.tax_rate} onChange={(e) => setProductForm({ ...productForm, tax_rate: e.target.value })} className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-black/10" />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Barcode</label>
                <input value={productForm.barcode} onChange={(e) => setProductForm({ ...productForm, barcode: e.target.value })} className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-black/10" />
              </div>
              <div className="flex gap-3 pt-2">
                <button type="button" onClick={() => setShowProductModal(false)} className="flex-1 px-4 py-2.5 rounded-xl border border-gray-200 text-sm font-medium text-gray-600 hover:bg-gray-50">Cancel</button>
                <button type="submit" disabled={createProduct.isPending || updateProduct.isPending} className="flex-1 px-4 py-2.5 rounded-xl bg-black text-white text-sm font-semibold hover:bg-zinc-800 disabled:opacity-50">
                  {createProduct.isPending || updateProduct.isPending ? "Saving..." : "Save"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Category Modal */}
      {showCategoryModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={() => setShowCategoryModal(false)}>
          <div className="bg-white rounded-2xl p-6 w-full max-w-md shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-bold text-gray-900 mb-4">New Category</h2>
            <form onSubmit={handleCategorySubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
                <input value={categoryForm.name} onChange={(e) => setCategoryForm({ ...categoryForm, name: e.target.value })} required className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-black/10" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Business Unit</label>
                <select value={categoryForm.business_unit} onChange={(e) => setCategoryForm({ ...categoryForm, business_unit: e.target.value as Category["business_unit"] })} className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm">
                  {BUSINESS_UNITS.slice(1).map((u) => <option key={u.value} value={u.value}>{u.label}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                <textarea value={categoryForm.description} onChange={(e) => setCategoryForm({ ...categoryForm, description: e.target.value })} className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-black/10" rows={3} />
              </div>
              <div className="flex gap-3 pt-2">
                <button type="button" onClick={() => setShowCategoryModal(false)} className="flex-1 px-4 py-2.5 rounded-xl border border-gray-200 text-sm font-medium text-gray-600 hover:bg-gray-50">Cancel</button>
                <button type="submit" disabled={createCategory.isPending} className="flex-1 px-4 py-2.5 rounded-xl bg-black text-white text-sm font-semibold hover:bg-zinc-800 disabled:opacity-50">
                  {createCategory.isPending ? "Saving..." : "Save"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Stock Adjustment Modal */}
      {showStockModal && stockTarget && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={() => setShowStockModal(false)}>
          <div className="bg-white rounded-2xl p-6 w-full max-w-md shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-bold text-gray-900 mb-1">Adjust Stock</h2>
            <p className="text-sm text-gray-500 mb-4">{stockTarget.name} (Current: {stockTarget.stock_quantity})</p>
            <form onSubmit={handleStockSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">New Quantity</label>
                <input type="number" step="0.001" value={stockForm.quantity} onChange={(e) => setStockForm({ ...stockForm, quantity: e.target.value })} required className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-black/10" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Reason</label>
                <input value={stockForm.reason} onChange={(e) => setStockForm({ ...stockForm, reason: e.target.value })} required placeholder="e.g. Delivery, Recount, Damage" className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-black/10" />
              </div>
              <div className="flex gap-3 pt-2">
                <button type="button" onClick={() => setShowStockModal(false)} className="flex-1 px-4 py-2.5 rounded-xl border border-gray-200 text-sm font-medium text-gray-600 hover:bg-gray-50">Cancel</button>
                <button type="submit" disabled={adjustStock.isPending} className="flex-1 px-4 py-2.5 rounded-xl bg-black text-white text-sm font-semibold hover:bg-zinc-800 disabled:opacity-50">
                  {adjustStock.isPending ? "Adjusting..." : "Adjust"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
