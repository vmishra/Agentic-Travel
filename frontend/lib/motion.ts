import type { Transition, Variants } from "motion/react";

/** The one motion curve — a calm spring used for every state transition. */
export const spring: Transition = {
  type: "spring",
  stiffness: 260,
  damping: 28,
  mass: 0.6,
};

export const quickOut: Transition = { duration: 0.18, ease: [0.2, 0.7, 0.2, 1] };

/** Entrance: a small rise, never more than 8px. */
export const fadeRise: Variants = {
  initial: { opacity: 0, y: 6 },
  animate: { opacity: 1, y: 0, transition: spring },
  exit: { opacity: 0, y: -4, transition: quickOut },
};

export const chipEnter: Variants = {
  initial: { opacity: 0, y: 4, scale: 0.96 },
  animate: { opacity: 1, y: 0, scale: 1, transition: { ...spring, stiffness: 320 } },
  exit: { opacity: 0, scale: 0.96, transition: quickOut },
};
