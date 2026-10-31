import { useState } from "react";

// Wraps an async API call with loading / error / data state.
// Usage: const [state, run] = useRequest(api.something); run(args)
export function useRequest(fn) {
  const [state, setState] = useState({ loading: false, error: null, data: null });

  const run = async (...args) => {
    setState({ loading: true, error: null, data: null });
    try {
      const data = await fn(...args);
      setState({ loading: false, error: null, data });
      return data;
    } catch (e) {
      setState({ loading: false, error: e.message, data: null });
    }
  };

  return [state, run];
}