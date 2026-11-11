import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { Loader2 } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

const button = cva(
  "inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-full text-[13px] font-medium transition-all duration-150 active:scale-[0.98] disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        primary: "bg-primary text-primary-ink hover:bg-primary-hover shadow-card",
        accent: "bg-accent text-accent-ink hover:bg-accent-hover shadow-card",
        secondary: "border border-line-strong bg-surface text-ink shadow-card hover:bg-surface-3",
        ghost: "text-ink-2 hover:bg-surface-3 hover:text-ink",
        danger: "border border-danger/30 bg-surface text-danger shadow-card hover:bg-danger-soft",
        subtle: "bg-surface-3 text-ink hover:bg-line",
        link: "h-auto px-0 text-accent underline-offset-2 hover:underline",
      },
      size: { sm: "h-7 px-3 text-[12px]", md: "h-9 px-4", lg: "h-10 px-5 text-[14px]", icon: "h-9 w-9" },
    },
    defaultVariants: { variant: "secondary", size: "md" },
  },
);

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof button> {
  asChild?: boolean;
  loading?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild, loading, children, disabled, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp ref={ref} className={cn(button({ variant, size }), className)} disabled={disabled || loading} {...props}>
        {asChild ? children : (<>{loading && <Loader2 className="animate-spin" />}{children}</>)}
      </Comp>
    );
  },
);
Button.displayName = "Button";
