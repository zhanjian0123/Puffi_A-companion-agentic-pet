import type { ReactNode } from 'react';

interface MarkdownMessageProps {
  content: string;
}

interface MarkdownBlock {
  type: 'paragraph' | 'heading' | 'unordered-list' | 'ordered-list' | 'code';
  content: string;
  items?: string[];
  level?: number;
  language?: string;
}

export function MarkdownMessage({ content }: MarkdownMessageProps) {
  const blocks = parseMarkdownBlocks(content);

  return (
    <div className="markdown-message">
      {blocks.map((block, index) => renderBlock(block, index))}
    </div>
  );
}

function renderBlock(block: MarkdownBlock, index: number) {
  switch (block.type) {
    case 'heading': {
      const Tag = (`h${Math.min(block.level ?? 1, 6)}` as keyof JSX.IntrinsicElements);
      return <Tag key={index}>{renderInlineMarkdown(block.content)}</Tag>;
    }
    case 'unordered-list':
      return (
        <ul key={index}>
          {(block.items ?? []).map((item, itemIndex) => (
            <li key={itemIndex}>{renderInlineMarkdown(item)}</li>
          ))}
        </ul>
      );
    case 'ordered-list':
      return (
        <ol key={index}>
          {(block.items ?? []).map((item, itemIndex) => (
            <li key={itemIndex}>{renderInlineMarkdown(item)}</li>
          ))}
        </ol>
      );
    case 'code':
      return (
        <pre key={index}>
          <code className={block.language ? `language-${block.language}` : undefined}>
            {block.content}
          </code>
        </pre>
      );
    case 'paragraph':
    default:
      return <p key={index}>{renderInlineMarkdown(block.content)}</p>;
  }
}

function parseMarkdownBlocks(markdown: string): MarkdownBlock[] {
  const lines = markdown.replace(/\r\n/g, '\n').split('\n');
  const blocks: MarkdownBlock[] = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];

    if (!line.trim()) {
      index += 1;
      continue;
    }

    const codeFenceMatch = line.match(/^```(\S+)?\s*$/);
    if (codeFenceMatch) {
      const codeLines: string[] = [];
      index += 1;
      while (index < lines.length && !/^```/.test(lines[index])) {
        codeLines.push(lines[index]);
        index += 1;
      }
      if (index < lines.length) {
        index += 1;
      }
      blocks.push({
        type: 'code',
        content: codeLines.join('\n'),
        language: codeFenceMatch[1],
      });
      continue;
    }

    const headingMatch = line.match(/^(#{1,6})\s+(.+)$/);
    if (headingMatch) {
      blocks.push({
        type: 'heading',
        level: headingMatch[1].length,
        content: headingMatch[2].trim(),
      });
      index += 1;
      continue;
    }

    if (/^\s*[-*+]\s+/.test(line)) {
      const items: string[] = [];
      while (index < lines.length && /^\s*[-*+]\s+/.test(lines[index])) {
        items.push(lines[index].replace(/^\s*[-*+]\s+/, '').trim());
        index += 1;
      }
      blocks.push({ type: 'unordered-list', content: '', items });
      continue;
    }

    if (/^\s*\d+\.\s+/.test(line)) {
      const items: string[] = [];
      while (index < lines.length && /^\s*\d+\.\s+/.test(lines[index])) {
        items.push(lines[index].replace(/^\s*\d+\.\s+/, '').trim());
        index += 1;
      }
      blocks.push({ type: 'ordered-list', content: '', items });
      continue;
    }

    const paragraphLines: string[] = [];
    while (
      index < lines.length &&
      lines[index].trim() &&
      !/^```/.test(lines[index]) &&
      !/^(#{1,6})\s+/.test(lines[index]) &&
      !/^\s*[-*+]\s+/.test(lines[index]) &&
      !/^\s*\d+\.\s+/.test(lines[index])
    ) {
      paragraphLines.push(lines[index].trim());
      index += 1;
    }

    blocks.push({
      type: 'paragraph',
      content: paragraphLines.join('\n'),
    });
  }

  return blocks;
}

function renderInlineMarkdown(text: string): ReactNode[] {
  const tokens = text.split(/(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\((?:https?:\/\/|mailto:)[^)]+\))/g);
  const nodes: ReactNode[] = [];

  tokens.forEach((token, index) => {
    if (!token) {
      return;
    }

    if (/^\*\*[^*]+\*\*$/.test(token)) {
      nodes.push(<strong key={index}>{token.slice(2, -2)}</strong>);
      return;
    }

    if (/^`[^`]+`$/.test(token)) {
      nodes.push(<code key={index}>{token.slice(1, -1)}</code>);
      return;
    }

    const linkMatch = token.match(/^\[([^\]]+)\]\(((?:https?:\/\/|mailto:)[^)]+)\)$/);
    if (linkMatch) {
      nodes.push(
        <a key={index} href={linkMatch[2]} target="_blank" rel="noreferrer">
          {linkMatch[1]}
        </a>
      );
      return;
    }

    const lines = token.split('\n');
    lines.forEach((line, lineIndex) => {
      if (line) {
        nodes.push(line);
      }
      if (lineIndex < lines.length - 1) {
        nodes.push(<br key={`${index}-${lineIndex}`} />);
      }
    });
  });

  return nodes;
}
