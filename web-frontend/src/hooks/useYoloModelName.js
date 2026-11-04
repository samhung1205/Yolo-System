import { useCallback, useEffect, useState } from "react";

import detectionService from "../services/detectionService";

// One registry request per page load; every page that names a model shares it.
let registryRequest = null;

function loadRegistry() {
  if (!registryRequest) {
    registryRequest = detectionService.listYoloModels().catch((error) => {
      registryRequest = null;
      throw error;
    });
  }
  return registryRequest;
}

/**
 * Returns `(modelKey, fallbackName) => label`, preferring the registry's
 * display name so a model is called the same thing everywhere. Records whose
 * key is unknown (or while the registry loads) fall back to the stored name.
 */
export default function useYoloModelName() {
  const [models, setModels] = useState([]);

  useEffect(() => {
    let active = true;
    loadRegistry()
      .then((items) => { if (active) setModels(items); })
      .catch(() => {});
    return () => { active = false; };
  }, []);

  return useCallback(
    (modelKey, fallbackName) =>
      models.find((model) => model.key === modelKey)?.display_name || fallbackName || modelKey || "-",
    [models]
  );
}
