export function useRouter() {
  return {
    push: (url?: string) => {
      void url;
      return undefined;
    }
  };
}

export function usePathname() {
  return '/';
}

export function useSearchParams() {
  return new URLSearchParams();
}
