import type { Post } from '../api/types';

const rtf = new Intl.RelativeTimeFormat('en', { numeric: 'auto' });

type RelativeUnit = 'year' | 'month' | 'week' | 'day' | 'hour' | 'minute' | 'second';

const UNITS: Array<[RelativeUnit, number]> = [
  ['year', 31_536_000],
  ['month', 2_592_000],
  ['week', 604_800],
  ['day', 86_400],
  ['hour', 3_600],
  ['minute', 60],
  ['second', 1],
];

export function relativeTime(iso: string): string {
  const timestamp = new Date(iso).getTime();
  if (Number.isNaN(timestamp)) {
    return '';
  }
  const diffSeconds = Math.round((timestamp - Date.now()) / 1000);
  const abs = Math.abs(diffSeconds);
  if (abs < 45) {
    return 'just now';
  }
  for (const [unit, seconds] of UNITS) {
    if (abs >= seconds) {
      return rtf.format(Math.round(diffSeconds / seconds), unit);
    }
  }
  return '';
}

function initials(username: string): string {
  return username.slice(0, 2).toUpperCase();
}

interface PostCardProps {
  post: Post;
}

export default function PostCard({ post }: PostCardProps) {
  const time = relativeTime(post.created_at);
  return (
    <article className="post-card">
      <span className="avatar" aria-hidden="true">
        {initials(post.author.username)}
      </span>
      <div className="post-body">
        <div className="post-meta">
          <span className="post-author">{post.author.username}</span>
          {time && (
            <time className="post-time" dateTime={post.created_at} title={new Date(post.created_at).toLocaleString()}>
              {time}
            </time>
          )}
        </div>
        <p className="post-content">{post.content}</p>
      </div>
    </article>
  );
}