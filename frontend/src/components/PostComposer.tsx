import axios from 'axios';
import { useState, type FormEvent, type RefObject } from 'react';

import { createPost } from '../api/posts';
import type { Post } from '../api/types';

const MAX_LENGTH = 500;

interface PostComposerProps {
  onPosted: (post: Post) => void;
  inputRef?: RefObject<HTMLTextAreaElement | null>;
}

export default function PostComposer({ onPosted, inputRef }: PostComposerProps) {
  const [content, setContent] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [rateLimited, setRateLimited] = useState(false);

  const trimmed = content.trim();
  const remaining = MAX_LENGTH - content.length;
  const nearLimit = remaining < 20;
  const overLimit = content.length > MAX_LENGTH;
  const canSubmit = trimmed.length > 0 && !overLimit && !isSubmitting;

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canSubmit) {
      return;
    }
    setIsSubmitting(true);
    setRateLimited(false);
    try {
      const post = await createPost(trimmed);
      setContent('');
      onPosted(post);
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 429) {
        setRateLimited(true);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const counterClass = overLimit
    ? 'character-count over-limit'
    : nearLimit
      ? 'character-count near-limit'
      : 'character-count';

  return (
    <form className="composer" onSubmit={handleSubmit}>
      {rateLimited && (
        <div className="alert" role="status">
          <span>Too many requests — try again in a moment.</span>
          <button
            type="button"
            className="alert-dismiss"
            aria-label="Dismiss"
            onClick={() => setRateLimited(false)}
          >
            ×
          </button>
        </div>
      )}
      <label className="sr-only" htmlFor="post-content">
        What&apos;s on your mind?
      </label>
      <textarea
        id="post-content"
        ref={inputRef}
        className="input composer-input"
        placeholder="What's on your mind?"
        value={content}
        maxLength={MAX_LENGTH + 1}
        onChange={(event) => setContent(event.target.value)}
        disabled={isSubmitting}
        aria-describedby="char-count"
      />
      <div className="composer-footer">
        <span id="char-count" className={counterClass} aria-live="polite">
          {remaining}/{MAX_LENGTH}
        </span>
        <button
          className="btn btn-primary"
          type="submit"
          disabled={!canSubmit}
          aria-disabled={!canSubmit}
        >
          {isSubmitting ? (
            <>
              <span className="spinner spinner-sm" aria-hidden="true" />
              Posting…
            </>
          ) : (
            'Post'
          )}
        </button>
      </div>
    </form>
  );
}