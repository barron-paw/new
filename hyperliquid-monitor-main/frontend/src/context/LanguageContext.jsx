import { createContext, useCallback, useContext, useState } from 'react';

const LANGUAGE_STORAGE_KEY = 'hm_language_preference';

const LanguageContext = createContext({
  language: 'zh',
  setLanguage: () => {},
});

export function LanguageProvider({ children }) {
  const [languageState, setLanguageState] = useState(() => {
    if (typeof window !== 'undefined' && window.localStorage) {
      const stored = window.localStorage.getItem(LANGUAGE_STORAGE_KEY);
      if (stored && ['zh', 'en'].includes(stored)) {
        return stored;
      }
    }
    return 'zh';
  });

  const setLanguage = useCallback((nextLanguage) => {
    const normalized = ['en'].includes(nextLanguage) ? 'en' : 'zh';
    setLanguageState(normalized);
    if (typeof window !== 'undefined' && window.localStorage) {
      window.localStorage.setItem(LANGUAGE_STORAGE_KEY, normalized);
    }
  }, []);

  return (
    <LanguageContext.Provider value={{ language: languageState, setLanguage }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  return useContext(LanguageContext);
}


