import type { AnchorHTMLAttributes, MouseEvent } from "react";
import { hrefOf, navigate, type Route } from "../router";

type Props = Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href"> & { to: Route; replace?: boolean };

/** An in-app link: a real <a href="#/..."> (open in new tab works) that navigates without reloading. */
export function Link({ to, replace, onClick, ...rest }: Props) {
  const go = (event: MouseEvent<HTMLAnchorElement>) => {
    onClick?.(event);
    if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return;
    event.preventDefault();
    navigate(to, { replace });
  };
  return <a href={hrefOf(to)} onClick={go} {...rest} />;
}
