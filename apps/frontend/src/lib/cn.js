import { clsx } from 'clsx'
import { extendTailwindMerge } from 'tailwind-merge'

/**
 * Custom font-size tokens (text-label-md, text-body-sm, …) must be classified as
 * font sizes — otherwise they collide with color utilities like text-on-primary
 * and strip white button text.
 */
const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      'font-size': [
        {
          text: [
            'body-sm',
            'body-md',
            'body-lg',
            'label-md',
            'display-lg',
            'display-lg-mobile',
            'headline-sm',
            'headline-md',
            'mono-sm',
          ],
        },
      ],
    },
  },
})

export function cn(...inputs) {
  return twMerge(clsx(inputs))
}
