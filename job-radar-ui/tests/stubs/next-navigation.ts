export function useRouter() {
  return {
    push: (_url: string) => {}
  };
}

export function usePathname() {
  return '/';
}

export function useSearchParams() {
  return new URLSearchParams();
}
