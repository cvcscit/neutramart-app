import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Menu } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { useAuth } from "@/contexts/AuthContext";
import logo from "@/assets/images/logo.jpeg";

export default function Navbar() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const { user, handleLogout } = useAuth();
  const navigate = useNavigate();
  const isAuthenticated = !!user;

  const logout = () => {
    handleLogout();
    navigate("/");
  };

  return (
    <header className="sticky top-0 z-100 w-full border-b bg-white">
      <div className="flex h-16 items-center justify-between px-4">
        {/* Logo */}
        <Link
          to={isAuthenticated ? "/dashboard" : "/"}
          className="flex items-center gap-3"
          onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
        >
          <img src={logo} alt="Logo" width={40} height={40} className="w-10" />
          <span className="text-2xl font-semibold text-green-700">
            NutraSmart
          </span>
        </Link>

        {/* Desktop Navigation */}
        <nav className="hidden md:flex items-center gap-6">
          {isAuthenticated ? (
            <>
              <Link
                to="/dashboard"
                className="text-sm font-medium text-gray-700 hover:text-green-700 transition-colors"
              >
                Dashboard
              </Link>
              <Link
                to="/upload"
                className="text-sm font-medium text-gray-700 hover:text-green-700 transition-colors"
              >
                Upload
              </Link>
              <a
                href="https://sylphiaconsulting.com/contact/"
                className="text-sm font-medium text-gray-700 hover:text-green-700 transition-colors"
              >
                Contact
              </a>
              <Button onClick={logout} variant="outline" size="sm">
                Logout
              </Button>
            </>
          ) : (
            <>
              <a
                href="https://sylphiaconsulting.com/our-mission/"
                className="text-sm font-medium text-gray-700 hover:text-green-700 transition-colors"
              >
                More About Us
              </a>

              <a
                href="https://sylphiaconsulting.com/contact/"
                className="text-sm font-medium text-gray-700 hover:text-green-700 transition-colors"
              >
                Contact
              </a>
              <Button asChild size="sm">
                <Link to="/login">Login</Link>
              </Button>
            </>
          )}
        </nav>

        {/* Mobile Menu */}
        <Sheet open={mobileMenuOpen} onOpenChange={setMobileMenuOpen}>
          <SheetTrigger asChild className="md:hidden">
            <Button variant="ghost" size="icon">
              <Menu className="h-6 w-6" />
              <span className="sr-only">Toggle menu</span>
            </Button>
          </SheetTrigger>
          <SheetContent side="right" className="w-[300px]">
            <SheetHeader>
              <SheetTitle className="text-3xl">Menu</SheetTitle>
            </SheetHeader>
            <nav className="flex flex-col gap-4 mt-7 pl-4 pr-4">
              {isAuthenticated ? (
                <>
                  <Link
                    to="/dashboard"
                    onClick={() => setMobileMenuOpen(false)}
                    className="text-base font-medium text-gray-700 hover:text-green-700 transition-colors py-2"
                  >
                    Dashboard
                  </Link>
                  <Link
                    to="/upload"
                    onClick={() => setMobileMenuOpen(false)}
                    className="text-base font-medium text-gray-700 hover:text-green-700 transition-colors py-2"
                  >
                    Profile
                  </Link>
                  <Link
                    to="/feedback"
                    onClick={() => setMobileMenuOpen(false)}
                    className="text-base font-medium text-gray-700 hover:text-green-700 transition-colors py-2"
                  >
                    Feedback
                  </Link>
                  <a
                    href="https://sylphiaconsulting.com/contact/"
                    onClick={() => setMobileMenuOpen(false)}
                    className="text-base font-medium text-gray-700 hover:text-green-700 transition-colors py-2"
                  >
                    Contact
                  </a>
                  <Button
                    onClick={() => {
                      logout();
                      setMobileMenuOpen(false);
                    }}
                    variant="outline"
                    className="w-full mt-4"
                  >
                    Logout
                  </Button>
                </>
              ) : (
                <>
                  <a
                    href="https://sylphiaconsulting.com/our-mission/"
                    onClick={() => setMobileMenuOpen(false)}
                    className="text-base font-medium text-gray-700 hover:text-green-700 transition-colors py-2"
                  >
                    More About Us
                  </a>
                  <Link
                    to="/feedback"
                    onClick={() => setMobileMenuOpen(false)}
                    className="text-base font-medium text-gray-700 hover:text-green-700 transition-colors py-2"
                  >
                    Feedback
                  </Link>
                  <a
                    href="https://sylphiaconsulting.com/contact/"
                    onClick={() => setMobileMenuOpen(false)}
                    className="text-base font-medium text-gray-700 hover:text-green-700 transition-colors py-2"
                  >
                    Contact
                  </a>
                  <Button asChild className="w-full mt-4">
                    <Link to="/login">Login</Link>
                  </Button>
                </>
              )}
            </nav>
          </SheetContent>
        </Sheet>
      </div>
    </header>
  );
}
