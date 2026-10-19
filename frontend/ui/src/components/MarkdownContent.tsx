import ReactMarkdown, { defaultUrlTransform } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { safeOfficialUrl } from '../lib/url';

interface Props { text: string; onCite?: (n: number) => void }

/**
 * Safe Markdown: raw HTML is never rendered (no rehype-raw), links are restricted to official JKLU hosts,
 * and inline citations like [1] become buttons that open the matching source.
 */
export function MarkdownContent({ text, onCite }: Props) {
  const prepared = text.replace(/\[(\d{1,2})\](?!\()/g, '[$1](cite:$1)');
  return (
    <div className="prose-jklu break-words">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        urlTransform={(url) => (url.startsWith('cite:') ? url : defaultUrlTransform(url))}
        components={{
          a({ href, children }) {
            if (href?.startsWith('cite:')) {
              const n = Number(href.slice(5));
              return (
                <button
                  type="button"
                  onClick={() => onCite?.(n)}
                  aria-label={`Open source ${n}`}
                  className="mx-0.5 inline-flex -translate-y-px items-center rounded-md border border-accent/30 bg-accent/10 px-1.5 font-mono text-[11.5px] font-medium text-accent-soft transition-colors hover:border-accent hover:bg-accent/20 hover:text-white"
                >
                  [{n}]
                </button>
              );
            }
            const safe = safeOfficialUrl(href);
            return safe ? <a href={safe} target="_blank" rel="noopener noreferrer">{children}</a> : <span>{children}</span>;
          },
          table({ children }) { return <div className="table-wrap"><table>{children}</table></div>; },
          img() { return null; },
        }}
      >
        {prepared}
      </ReactMarkdown>
    </div>
  );
}
