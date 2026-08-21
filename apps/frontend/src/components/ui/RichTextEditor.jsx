import { useEffect } from 'react'
import { EditorContent, useEditor } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'
import { Label } from './Input'
import { cn } from '../../lib/cn'

function toEditorHtml(value) {
  if (!value) return ''
  if (/<[a-z][\s\S]*>/i.test(value)) return value
  const escaped = value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  return `<p>${escaped.replace(/\n/g, '<br>')}</p>`
}

function htmlFromEditor(editor) {
  if (!editor || editor.isEmpty) return ''
  return editor.getHTML()
}

function ToolButton({ label, icon, active, onClick }) {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      aria-pressed={active}
      onMouseDown={(event) => event.preventDefault()}
      onClick={onClick}
      className={cn(
        'inline-flex h-8 w-8 items-center justify-center rounded-lg text-on-surface-variant',
        'hover:bg-surface-container-low hover:text-on-surface',
        active && 'bg-primary-container text-on-primary-container',
      )}
    >
      <span className="material-symbols-outlined text-[18px]">{icon}</span>
    </button>
  )
}

export function RichTextEditor({
  id,
  label,
  value,
  onChange,
  placeholder,
  disabled = false,
}) {
  const editor = useEditor({
    immediatelyRender: false,
    shouldRerenderOnTransaction: true,
    editable: !disabled,
    extensions: [
      StarterKit.configure({
        heading: { levels: [2, 3] },
        code: false,
        codeBlock: false,
        blockquote: false,
        horizontalRule: false,
        link: false,
      }),
      Placeholder.configure({ placeholder: placeholder || '' }),
    ],
    content: toEditorHtml(value),
    editorProps: {
      attributes: {
        id: id || 'rich-text-editor',
        class: 'rich-text min-h-[160px] px-md py-sm text-body-sm text-on-surface outline-none',
      },
    },
    onUpdate: ({ editor: instance }) => {
      onChange?.(htmlFromEditor(instance))
    },
  })

  useEffect(() => {
    if (!editor) return
    editor.setEditable(!disabled)
  }, [disabled, editor])

  return (
    <div>
      {label ? <Label htmlFor={id}>{label}</Label> : null}
      <div
        className={cn(
          'rounded-xl border border-outline-variant/80 bg-surface-container-lowest overflow-hidden shadow-soft',
          'focus-within:ring-2 focus-within:ring-primary/35 focus-within:border-primary',
          disabled && 'opacity-60 pointer-events-none',
        )}
      >
        <div className="flex flex-wrap gap-xs px-sm py-xs border-b border-outline-variant bg-surface-container-low">
          <ToolButton
            label="Bold"
            icon="format_bold"
            active={editor?.isActive('bold')}
            onClick={() => editor?.chain().focus().toggleBold().run()}
          />
          <ToolButton
            label="Italic"
            icon="format_italic"
            active={editor?.isActive('italic')}
            onClick={() => editor?.chain().focus().toggleItalic().run()}
          />
          <ToolButton
            label="Heading"
            icon="title"
            active={editor?.isActive('heading', { level: 2 })}
            onClick={() => editor?.chain().focus().toggleHeading({ level: 2 }).run()}
          />
          <ToolButton
            label="Bulleted list"
            icon="format_list_bulleted"
            active={editor?.isActive('bulletList')}
            onClick={() => editor?.chain().focus().toggleBulletList().run()}
          />
          <ToolButton
            label="Numbered list"
            icon="format_list_numbered"
            active={editor?.isActive('orderedList')}
            onClick={() => editor?.chain().focus().toggleOrderedList().run()}
          />
        </div>
        <EditorContent editor={editor} />
      </div>
    </div>
  )
}
