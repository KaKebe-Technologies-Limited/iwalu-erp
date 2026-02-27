import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Merges Tailwind classes without style conflicts and
 * allows for easy conditional class toggling.
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
