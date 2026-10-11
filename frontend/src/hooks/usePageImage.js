import { useEffect, useState } from "react";
import { fetchPageImage } from "../lib/api";

/** The screenshot of one parsed page: { url, error, loading }. error: "gone" | message. */
export function usePageImage(image) {
  const [state, setState] = useState({ url: null, error: null, loading: !!image });
  const taskId = image?.taskId;
  const number = image?.number;

  useEffect(() => {
    if (taskId == null) {
      setState({ url: null, error: null, loading: false });
      return undefined;
    }
    let active = true;
    let objectUrl = null;
    setState({ url: null, error: null, loading: true });
    fetchPageImage(taskId, number)
      .then((url) => {
        objectUrl = url;
        if (active) setState({ url, error: null, loading: false });
        else URL.revokeObjectURL(url);
      })
      .catch((err) => {
        if (active)
          setState({
            url: null,
            error: err.status === 410 ? "gone" : err.message,
            loading: false,
          });
      });
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [taskId, number]);

  return state;
}
