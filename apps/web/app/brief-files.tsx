'use client';

import { useEffect, useState } from 'react';

export function FilePreview({ file, onRemove }: { file: File; onRemove: () => void }) {
  const [url, setUrl] = useState('');
  useEffect(() => {
    const objectUrl = URL.createObjectURL(file);
    // eslint-disable-next-line react-hooks/set-state-in-effect -- Browser resource created and released with the mounted preview.
    setUrl(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [file]);
  const isImage = /\.(jpe?g|png|webp|gif)$/i.test(file.name);
  const isPdf = /\.pdf$/i.test(file.name);
  return (
    <li>
      {isImage && url && <img className="file-preview" src={url} alt={`Preview of ${file.name}`} /> /* eslint-disable-line @next/next/no-img-element */}
      <span><strong>{file.name}</strong><small>{file.size < 1024 ? `${file.size} B` : `${(file.size / 1024 / 1024).toFixed(2)} MiB`}</small>
        {url && (isImage || isPdf
          ? <a href={url} target="_blank" rel="noopener noreferrer">Open {isPdf ? 'PDF' : 'image'}</a>
          : <a href={url} download={file.name}>Download</a>)}
      </span>
      <button type="button" onClick={onRemove} aria-label={`Remove ${file.name}`}>Remove ×</button>
    </li>
  );
}
