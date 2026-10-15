import { createContext, useCallback, useContext, useState } from "react";

export const AssistantStateContext = createContext(null);

export function updateWorkspace(state, { page, field, value, initial }) {
  const previous = Object.hasOwn(state[page], field) ? state[page][field] : initial;
  const next = typeof value === "function" ? value(previous) : value;
  if (Object.hasOwn(state[page], field) && Object.is(previous, next)) return state;
  return { ...state, [page]: { ...state[page], [field]: next } };
}

// Memory belongs to this workspace, never browser storage. Leaving the
// workspace (including logout) discards both independent conversation drafts.
export function useAssistantState(page, field, initialValue) {
  const { state, dispatch } = useContext(AssistantStateContext);
  const [initial] = useState(initialValue);
  const value = Object.hasOwn(state[page], field) ? state[page][field] : initial;
  const setValue = useCallback((next) => {
    dispatch({ page, field, value: next, initial });
  }, [dispatch, page, field, initial]);
  return [value, setValue];
}

