import Image from "next/image";

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen flex bg-gray-50">
      {/* Left Panel - Image & Branding */}
      <div className="hidden lg:flex lg:w-1/2 relative overflow-hidden">
        {/* Background image */}
        <div
          className="absolute inset-0 z-0"
          style={{
            backgroundImage: "url('/office.jpeg')",
            backgroundSize: "cover",
            backgroundPosition: "center",
          }}
        />
        
        {/* Gradient overlay */}
        <div className="absolute inset-0 bg-gradient-to-br from-black/80 via-black/60 to-black/90 z-0" />

        {/* Content */}
        <div className="relative z-10 flex flex-col justify-between p-12 w-full">
          {/* Logo */}
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 bg-white/20 backdrop-blur-sm rounded-lg flex items-center justify-center border border-white/20">
              <span className="text-white font-bold text-xl">N</span>
            </div>
            <span className="text-white font-bold text-xl tracking-tight">Nexus ERP</span>
          </div>

          {/* Quote */}
          <div className="max-w-md">
            <blockquote className="text-white/90 text-xl font-medium leading-relaxed mb-4">
              &ldquo;Nexus transformed how we manage our 12 fuel stations. Reconciliation that used to take a full day now takes minutes.&rdquo;
            </blockquote>
            <cite className="text-white/60 text-sm not-italic">
              — James Mwangi, Operations Director, PetroLink Kenya
            </cite>
          </div>

          {/* Bottom text */}
          <div className="text-white/40 text-xs">
            © {new Date().getFullYear()} Nexus ERP. All rights reserved.
          </div>
        </div>
      </div>

      {/* Right Panel - Auth Form */}
      <div className="w-full lg:w-1/2 flex items-center justify-center p-6 sm:p-12 bg-white">
        <div className="w-full max-w-md animate-fade-in">
          {children}
        </div>
      </div>
    </div>
  );
}
