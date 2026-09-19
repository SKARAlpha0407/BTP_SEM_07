187fe359 checkpoint: pre-UI-polish (backend green, Groq live, ReadingMap ssr fix in place)

## Visual Weaknesses
- **Header**: Too utilitarian; lack of depth or visual hierarchy in the search area.
- **Synthesis Section**: The `bg-blue-50` box is generic; lacks a "premium" feel for the primary insight.
- **Paper List**: The 4/8 grid split is rigid; list items are visually repetitive with thin borders.
- **Paper Detail**: Over-reliance on `bg-gray-50` for every sub-section (TL;DR, Problem, Methods, Benchmarks) creates a "blocky" and monotonous appearance.
- **Benchmarks Table**: Lacks visual structure; text-heavy and lacks clear row separation or header emphasis.
- **Pipeline**: Static color-switching for steps; lacks a sense of "motion" or active state.
- **Empty State**: The landing page "📚" is too sparse.

## Class Strings to Target
- **Header**: `border-b border-gray-100 py-6 px-8` (frontend/pages/index.tsx:43)
- **Search Bar**: `flex gap-2 w-1/3` (frontend/pages/index.tsx:45)
- **Synthesis Box**: `bg-blue-50 p-6 rounded-2xl border border-blue-100` (frontend/pages/index.tsx:74)
- **Paper List Item**: `p-4 rounded-xl cursor-pointer border transition-all` (frontend/pages/index.tsx:86)
- **Detail Cards**: `p-4 bg-gray-50 rounded-xl border border-gray-100` (frontend/pages/index.tsx:117, 122, 126, 132)
- **Benchmarks Table**: `w-full text-xs text-left` (frontend/pages/index.tsx:134)
- **Pipeline Dot**: `w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-colors` (frontend/components/Pipeline.tsx:12)
- **Pipeline Line**: `flex-1 h-0.5 mx-2 transition-colors` (frontend/components/Pipeline.tsx:22)

## Unclear Elements
- `animate-in fade-in slide-in-from-bottom-2 duration-300` (frontend/pages/index.tsx:106): Purpose is a transition, but depends on specific Tailwind plugins (tailwindcss-animate) which may not be configured.
