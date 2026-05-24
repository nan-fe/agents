const DEFAULT_API_UPSTREAM = 'http://localhost:8000';

export const getApiUpstreamUrl = (): string => {
  const raw =
    process.env.API_UPSTREAM_URL ??
    process.env.API_BASE_URL ??
    DEFAULT_API_UPSTREAM;
  return raw.replace(/\/$/, '');
};
