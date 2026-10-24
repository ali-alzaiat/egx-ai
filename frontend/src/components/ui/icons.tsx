import type { ReactNode, SVGProps } from "react";

/*
 * Inline 16px icons, 1.5px stroke, currentColor (spec section 3.10). Icons are
 * for actions only; navigation stays text. Only `ChevronIcon` mirrors in RTL.
 */

type IconProps = Omit<SVGProps<SVGSVGElement>, "children"> & { size?: number };

function Svg({ size = 16, children, ...rest }: IconProps & { children: ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...rest}
    >
      {children}
    </svg>
  );
}

export function SearchIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="7" cy="7" r="4.5" />
      <path d="M10.5 10.5 14 14" />
    </Svg>
  );
}

export function MenuIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M2 4h12M2 8h12M2 12h12" />
    </Svg>
  );
}

export function CloseIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="m3.5 3.5 9 9M12.5 3.5l-9 9" />
    </Svg>
  );
}

export function SortIcon({ sort, ...props }: IconProps & { sort?: "asc" | "desc" | null }) {
  return (
    <Svg {...props}>
      <path d="M5 6.5 8 3.5l3 3" opacity={sort === "desc" ? 0.3 : 1} />
      <path d="M5 9.5 8 12.5l3-3" opacity={sort === "asc" ? 0.3 : 1} />
    </Svg>
  );
}

export function ExternalLinkIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M9 2.5h4.5V7M13.5 2.5 7.5 8.5M12 9.5v3a1 1 0 0 1-1 1H3.5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h3" />
    </Svg>
  );
}

export function InfoIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="8" cy="8" r="6" />
      <path d="M8 7.5v3.5M8 5v.01" />
    </Svg>
  );
}

export function WarningIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M8 2.5 14 13H2L8 2.5Z" />
      <path d="M8 6.5v3M8 11.3v.01" />
    </Svg>
  );
}

/** Points toward the inline end; mirrors under `[dir=rtl]` through the `.chevron` class. */
export function ChevronIcon({ className, ...props }: IconProps) {
  return (
    <Svg className={className ? `chevron ${className}` : "chevron"} {...props}>
      <path d="m6 3.5 4.5 4.5L6 12.5" />
    </Svg>
  );
}

export function TriangleUpIcon(props: IconProps) {
  return (
    <Svg {...props} fill="currentColor" stroke="none">
      <path d="M8 3.5 13 12H3L8 3.5Z" />
    </Svg>
  );
}

export function TriangleDownIcon(props: IconProps) {
  return (
    <Svg {...props} fill="currentColor" stroke="none">
      <path d="M8 12.5 3 4h10l-5 8.5Z" />
    </Svg>
  );
}

export function BarIcon(props: IconProps) {
  return (
    <Svg {...props} fill="currentColor" stroke="none">
      <rect x="3" y="7" width="10" height="2" rx="1" />
    </Svg>
  );
}
