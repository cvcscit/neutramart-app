import { useState, useEffect } from "react";
import { ArrowUpRight, ArrowRight, UtensilsCrossed } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Separator } from "@/components/ui/separator";
import { Link } from "react-router-dom";
import logoTransparent from "@/assets/images/logo-transparent.png";

// ─── Types ───────────────────────────────────────────────────────────────────

interface FooterLink {
  label: string;
  href: string;
  external?: boolean;
}

interface FooterColumnData {
  id: string;
  title: string;
  links: FooterLink[];
}

interface TimeState {
  hour: string;
  minute: string;
  second: string;
}

// ─── Data ────────────────────────────────────────────────────────────────────

const footerColumns: FooterColumnData[] = [
  {
    id: "products",
    title: "Products",
    links: [
      { label: "Nutrition App", href: "/products/nutrition-app" },
      { label: "SAAS Application", href: "/products/saas" },
      { label: "Cybersecurity app", href: "/products/cybersecurity" },
    ],
  },
  {
    id: "information",
    title: "Information",
    links: [
      { label: "Custom solutions", href: "/custom-solutions" },
      { label: "Sustainability", href: "/sustainability" },
      { label: "Our story", href: "/about-us" },
      { label: "Insights", href: "/insights" },
    ],
  },
  {
    id: "social-media",
    title: "Social media",
    links: [
      {
        label: "Website",
        href: "https://sylphiaconsulting.com/",
        external: true,
      },
      {
        label: "LinkedIn",
        href: "https://www.linkedin.com/company/sylphiaconsulting/?originalSubdomain=ca",
        external: true,
      },
    ],
  },
];

const legalLinks = [
  { label: "Privacy policy", shortLabel: "Privacy", href: "/privacy-policy" },
  { label: "Cookie policy", shortLabel: "Cookies", href: "/cookie-policy" },
  {
    label: "Terms & conditions",
    shortLabel: "Terms",
    href: "/terms-and-conditions",
  },
];

// ─── Main Footer ─────────────────────────────────────────────────────────────

export default function CustomFooter() {
  const [time1, setTime1] = useState<TimeState>({
    hour: "00",
    minute: "00",
    second: "00",
  });
  const [time2, setTime2] = useState<TimeState>({
    hour: "00",
    minute: "00",
    second: "00",
  });
  const [currentYear, setCurrentYear] = useState("2025");

  useEffect(() => {
    setCurrentYear(new Date().getFullYear().toString());

    const updateTimes = () => {
      const usTime = new Date().toLocaleString("en-US", {
        timeZone: "America/New_York",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      });
      const [usHour, usMinute, usSecond] = usTime.split(":");
      setTime1({ hour: usHour!, minute: usMinute!, second: usSecond! });

      const caTime = new Date().toLocaleString("en-US", {
        timeZone: "America/Toronto",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      });
      const [caHour, caMinute, caSecond] = caTime.split(":");
      setTime2({ hour: caHour!, minute: caMinute!, second: caSecond! });
    };

    updateTimes();
    const interval = setInterval(updateTimes, 1000);

    return () => clearInterval(interval);
  }, []);

  return (
    <footer className="bg-green-900 text-stone-50 pt-12 md:pt-16 pb-6 md:pb-[18px] overflow-hidden relative z-50">
      <div className="container mx-auto px-4">
        <div className="grid grid-cols-4 md:grid-cols-12 gap-4">
          {/* Tagline */}
          <div className="col-span-full md:col-span-3 text-[20px] leading-[140%] text-stone-50">
            We help you eat better, not by changing who you are, but by helping
            you understand what fuels you. Because nutrition isn't just about
            numbers — it's about balance, awareness, and feeling your best every
            day.
          </div>

          {/* Navigation Columns */}
          <nav
            className="col-span-full md:col-start-5 md:col-span-8 flex flex-col md:flex-row items-stretch md:items-start md:justify-between mt-10 md:mt-0"
            aria-label="Primary footer menu"
          >
            <Separator className="md:hidden bg-stone-50/20 mb-0" />

            {/* Desktop Navigation */}
            <div className="hidden md:flex w-full justify-between">
              {footerColumns.map((column) => (
                <FooterColumn key={column.id} column={column} />
              ))}
            </div>

            {/* Mobile Navigation */}
            <div className="md:hidden w-full">
              {footerColumns.map((column) => (
                <FooterColumnMobile key={column.id} column={column} />
              ))}
            </div>
          </nav>

          {/* Desktop Bottom Section */}
          <div className="hidden md:flex col-span-full md:col-span-12 flex-row flex-wrap items-end justify-between">
            {/* Logo */}
            <div className="flex-shrink-0 w-[40.6%] mr-[106px]">
              <div className="mt-[200px] relative">
                <Link to="/" className="block">
                  <img
                    src={logoTransparent}
                    alt="Sylphia Logo"
                    width={566}
                    height={89}
                    className="w-full h-auto"
                  />
                </Link>
              </div>
            </div>

            {/* Contact Info & Icon */}
            <div className="flex-1 flex flex-row items-end mt-10">
              <div className="flex-1 flex flex-row items-end justify-between">
                <Button
                  asChild
                  variant="outline"
                  className="bg-transparent border-stone-50 text-stone-50 hover:bg-stone-50 hover:text-green-900"
                >
                  <a href="https://sylphiaconsulting.com/contact/">
                    Contact us
                    <ArrowRight className="w-4 h-4 ml-2" />
                  </a>
                </Button>

                <TimeZone label="Canada" time={time2} phone="+1-XXX-XXX-XXXX" />

                <TimeZone
                  label="United States"
                  time={time1}
                  phone="+1-484-224-2972"
                />
              </div>

              <div className="flex-shrink-0 w-[58px] ml-[140px]">
                <UtensilsCrossed className="size-16 text-stone-50" />
              </div>
            </div>
          </div>

          {/* Mobile Bottom Section */}
          <div className="md:hidden col-span-full grid grid-cols-4 gap-4 mt-16">
            <div className="col-span-2 flex flex-col items-start justify-between gap-4">
              <Button
                asChild
                variant="outline"
                className="border-stone-50 text-stone-50 hover:bg-stone-50 hover:text-green-900 bg-transparent"
              >
                <a href="https://sylphiaconsulting.com/contact/">
                  Contact us
                  <ArrowRight className="w-4 h-4 ml-2" />
                </a>
              </Button>

              <div className="w-[38px]">
                <UtensilsCrossed className="w-full h-auto text-stone-50" />
              </div>
            </div>

            <div className="col-span-2 flex flex-col items-start gap-6 text-[0.6875rem] leading-[1.125rem] tracking-[0.055em] uppercase text-stone-50">
              <TimeZoneMobile
                label="United States"
                time={time1}
                phone="+1-484-224-2972"
              />
              <TimeZoneMobile
                label="Canada"
                time={time2}
                phone="+1-XXX-XXX-XXXX"
              />
            </div>

            <div className="col-span-2 text-[0.6875rem] leading-[1.125rem] tracking-[0.055em] uppercase text-stone-50">
              <span>NutraSmart © {currentYear}</span>
            </div>

            <div className="col-span-2 text-[0.6875rem] leading-[1.125rem] tracking-[0.055em] uppercase text-stone-50">
              <span>
                Site by{" "}
                <a
                  href="https://sylphiaconsulting.com/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="underline underline-offset-[3px] text-stone-50"
                >
                  Sylphia Consulting
                </a>
              </span>
            </div>
          </div>

          {/* Mobile Logo */}
          <div className="md:hidden col-span-full mt-10">
            <Link to="/" className="block">
              <div className="w-full h-[54px] bg-stone-50/10 rounded flex items-center justify-center text-xl font-semibold">
                NutraSmart
              </div>
            </Link>
          </div>
        </div>

        {/* Legal Links */}
        <nav
          className="container md:pt-[18px] mt-10 md:mt-8 text-center"
          aria-label="Secondary footer menu"
        >
          <Separator className="hidden md:block bg-stone-50/10 mb-[18px]" />
          <ul className="flex flex-row flex-wrap items-center justify-center gap-4 md:gap-y-4 text-[0.6875rem] leading-[1.125rem] tracking-[0.055em] uppercase whitespace-nowrap text-stone-50">
            <li className="hidden md:block">
              <span>Sylphia © {currentYear}</span>
            </li>

            <li
              className="hidden md:block flex-1 pointer-events-none opacity-60 after:content-['/']"
              aria-hidden="true"
            ></li>

            {legalLinks.map((link, index) => (
              <div key={link.href} className="flex items-center gap-4">
                <li>
                  <a
                    href={link.href}
                    className="underline hover:no-underline underline-offset-[3px] text-stone-50"
                  >
                    <span className="hidden md:inline">{link.label}</span>
                    <span className="md:hidden">{link.shortLabel}</span>
                  </a>
                </li>
                {index < legalLinks.length - 1 && (
                  <li
                    className="flex-1 pointer-events-none opacity-60 after:content-['/']"
                    aria-hidden="true"
                  ></li>
                )}
              </div>
            ))}

            <li
              className="hidden md:block flex-1 pointer-events-none opacity-60 after:content-['/']"
              aria-hidden="true"
            ></li>

            <li className="hidden md:block">
              <span>
                Site by{" "}
                <a
                  href="https://sylphiaconsulting.com/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="underline hover:no-underline underline-offset-[3px] text-stone-50"
                >
                  Sylphia Consulting
                </a>
              </span>
            </li>
          </ul>
        </nav>
      </div>
    </footer>
  );
}

// ─── Sub-components ──────────────────────────────────────────────────────────

interface FooterColumnProps {
  column: FooterColumnData;
}

function FooterColumn({ column }: FooterColumnProps) {
  return (
    <div className="w-[11.6%] flex flex-col items-start">
      <h2 className="mb-4 text-[0.6875rem] leading-[1.125rem] tracking-[0.055em] uppercase text-stone-50">
        {column.title}
      </h2>
      <ul className="flex flex-col items-start gap-3 text-[0.875rem] leading-[1.125rem] tracking-[0.01em] whitespace-nowrap">
        {column.links.map((link: FooterLink) => (
          <li key={link.href} className="w-full">
            <a
              href={link.href}
              className="group inline-flex items-center gap-1 text-stone-50 border-b-2 border-transparent hover:border-stone-50 transition-colors duration-300"
              {...(link.external && {
                target: "_blank",
                rel: "noopener noreferrer",
              })}
            >
              <span>{link.label}</span>
              <ArrowUpRight className="w-4 h-4 opacity-0 rotate-45 group-hover:opacity-100 group-hover:rotate-0 transition-all duration-300" />
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}

function FooterColumnMobile({ column }: FooterColumnProps) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <Collapsible
      open={isOpen}
      onOpenChange={setIsOpen}
      className="w-full border-b border-stone-50/20"
    >
      <CollapsibleTrigger className="w-full text-left py-6 text-[1.0625rem] leading-[1.375rem] tracking-[0.02em] text-stone-50 flex items-center justify-between">
        {column.title}
        <span className="w-4 h-4 relative">
          <span className="absolute top-1/2 left-0 w-full -translate-y-1/2 h-px bg-stone-50"></span>
          <span
            className={`absolute top-1/2 left-0 w-full -translate-y-1/2 h-px bg-stone-50 rotate-90 transition-opacity duration-300 ${
              isOpen ? "opacity-0" : ""
            }`}
          ></span>
        </span>
      </CollapsibleTrigger>
      <CollapsibleContent className="pb-6">
        <ul className="flex flex-col items-start gap-3 text-[0.875rem] leading-[1.125rem] tracking-[0.01em]">
          {column.links.map((link: FooterLink) => (
            <li key={link.href} className="w-full">
              <a
                href={link.href}
                className="group inline-flex items-center gap-1 text-stone-50 border-b-2 border-transparent hover:border-stone-50 transition-colors duration-300"
                {...(link.external && {
                  target: "_blank",
                  rel: "noopener noreferrer",
                })}
              >
                <span>{link.label}</span>
                <ArrowUpRight className="w-4 h-4 opacity-0 rotate-45 group-hover:opacity-100 group-hover:rotate-0 transition-all duration-300" />
              </a>
            </li>
          ))}
        </ul>
      </CollapsibleContent>
    </Collapsible>
  );
}

interface TimeZoneProps {
  label: string;
  time: TimeState;
  phone: string;
}

function TimeZone({ label, time, phone }: TimeZoneProps) {
  return (
    <div className="flex flex-col items-start text-[0.6875rem] leading-[1.125rem] tracking-[0.055em] uppercase text-stone-50">
      <span>{label}</span>
      <span className="flex items-center gap-[5px]">
        <span>{time.hour}</span>
        <span>:</span>
        <span>{time.minute}</span>
        <span>:</span>
        <span>{time.second}</span>
      </span>
      <a
        href={`tel:${phone}`}
        className="border-b-2 border-transparent hover:border-stone-50 transition-colors duration-300 text-stone-50"
      >
        {phone}
      </a>
    </div>
  );
}

function TimeZoneMobile({ label, time, phone }: TimeZoneProps) {
  return (
    <div className="flex flex-col items-start text-stone-50">
      <span>{label}</span>
      <span className="flex items-center gap-[5px]">
        <span>{time.hour}</span>
        <span>:</span>
        <span>{time.minute}</span>
        <span>:</span>
        <span>{time.second}</span>
      </span>
      <a
        href={`tel:${phone}`}
        className="border-b-2 border-transparent hover:border-stone-50 transition-colors duration-300 text-stone-50"
      >
        {phone}
      </a>
    </div>
  );
}
