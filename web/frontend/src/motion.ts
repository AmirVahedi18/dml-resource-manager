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
