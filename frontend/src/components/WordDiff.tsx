import React from 'react';
import * as Diff from 'diff';

interface WordDiffProps {
  originalText: string;
  proposedText: string;
  className?: string;
}

export const WordDiff: React.FC<WordDiffProps> = ({ originalText, proposedText, className = '' }) => {
  const diffParts = Diff.diffWordsWithSpace(originalText, proposedText);

  return (
    <div className={`font-sans leading-relaxed text-slate-800 whitespace-pre-wrap ${className}`}>
      {diffParts.map((part, index) => {
        if (part.added) {
          return (
            <ins
              key={index}
              className="bg-emerald-100 text-emerald-900 font-medium no-underline rounded px-1 py-0.5"
            >
              {part.value}
            </ins>
          );
        }
        if (part.removed) {
          return (
            <del
              key={index}
              className="bg-rose-100 text-rose-800 line-through rounded px-1 py-0.5 opacity-80"
            >
              {part.value}
            </del>
          );
        }
        return <span key={index}>{part.value}</span>;
      })}
    </div>
  );
};
