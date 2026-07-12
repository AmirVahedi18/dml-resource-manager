import type { Variants } from 'framer-motion';

/** Plain fade — banners, empty-states, skeleton/content swaps. */
export const fadeVariants: Variants = {
  initial: { opacity: 0 },
  animate: { opacity: 1, transition: { duration: 0.14, ease: 'easeOut' } },
  exit: { opacity: 0, transition: { duration: 0.1, ease: 'easeIn' } },
};

/** Fade + small upward shift — popovers, panels, list/table rows. */
export const fadeSlideVariants: Variants = {
  initial: { opacity: 0, y: -4 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.14, ease: 'easeOut' } },
  exit: { opacity: 0, y: -4, transition: { duration: 0.1, ease: 'easeIn' } },
};

/** Fade + scale — the confirm dialog, replaces the old modal-pop-in keyframes. */
export const modalVariants: Variants = {
  initial: { opacity: 0, scale: 0.96, y: 4 },
  animate: { opacity: 1, scale: 1, y: 0, transition: { duration: 0.14, ease: 'easeOut' } },
  exit: { opacity: 0, scale: 0.96, y: 4, transition: { duration: 0.1, ease: 'easeIn' } },
};

/** Fade + slide from the right — toasts, replaces the old toast-slide-in keyframes. */
export const toastVariants: Variants = {
  initial: { opacity: 0, x: 12 },
  animate: { opacity: 1, x: 0, transition: { duration: 0.16, ease: 'easeOut' } },
  exit: { opacity: 0, x: 12, transition: { duration: 0.12, ease: 'easeIn' } },
};

/**
 * Route/page transition — the previous page fades away in place (no movement), then the next
 * page emerges with a gentle rise. Exit and enter are deliberately *different* so it reads as
 * one continuous "old dissolves → new arrives" motion rather than the same transition twice.
 * Paired with `<AnimatePresence mode="wait">` so the pages never overlap (avoids scroll jank).
 */
export const pageVariants: Variants = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.24, ease: 'easeOut' } },
  exit: { opacity: 0, transition: { duration: 0.12, ease: 'easeIn' } },
};

/** Fade + gentle spring pop — card/panel entrances that should feel a touch lively. */
export const cardVariants: Variants = {
  initial: { opacity: 0, scale: 0.98, y: 8 },
  animate: {
    opacity: 1,
    scale: 1,
    y: 0,
    transition: { type: 'spring', stiffness: 320, damping: 26, mass: 0.7 },
  },
  exit: { opacity: 0, scale: 0.98, y: 6, transition: { duration: 0.1, ease: 'easeIn' } },
};

/**
 * Stagger container — drives its children (which use `staggerItem`) in sequence on mount.
 * Children must NOT set their own `initial`/`animate` props; they inherit the state names
 * from this parent so the stagger timing applies. Reduced motion is handled globally by
 * the app-level `<MotionConfig reducedMotion="user">`.
 */
export const staggerContainer: Variants = {
  initial: {},
  animate: { transition: { staggerChildren: 0.04, delayChildren: 0.02 } },
  exit: {},
};

/** A single staggered list/grid item — fade + small rise. Pair with `staggerContainer`. */
export const staggerItem: Variants = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.18, ease: 'easeOut' } },
  exit: { opacity: 0, y: -4, transition: { duration: 0.1, ease: 'easeIn' } },
};
