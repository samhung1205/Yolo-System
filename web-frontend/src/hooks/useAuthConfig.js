import { useEffect, useState } from "react";
import authService from "../services/authService";

export default function useAuthConfig() {
  const [registrationEnabled, setRegistrationEnabled] = useState(null);
  const [configError, setConfigError] = useState("");

  useEffect(() => {
    let active = true;
    authService.fetchConfig().then((config) => {
      if (active) setRegistrationEnabled(config.registration_enabled === true);
    }).catch(() => {
      if (active) {
        setRegistrationEnabled(false);
        setConfigError("暫時無法確認帳號申請方式，請稍後再試或聯絡管理員。");
      }
    });
    return () => { active = false; };
  }, []);

  return { registrationEnabled, configError };
}
