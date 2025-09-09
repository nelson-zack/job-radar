#!/usr/bin/env bash
# Helper to detect which ATS a company's careers page uses.
# Usage: ./scripts/detect_ats.sh <careers-or-root-url> [Company Name]

set -euo pipefail

UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
ACCT="text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"

normalize_url() {
  local u="$1"
  [[ "$u" == http* ]] || u="https://$u"
  echo "$u"
}

fetch_html() {
  local url="$1"
  curl -Ls --compressed -A "$UA" -H "Accept: $ACCT" --max-time 15 "$url" || true
}

fetch_heads() {
  local url="$1"
  # follow redirects and print the chain of Location headers
  curl -ILs --compressed -A "$UA" -H "Accept: $ACCT" --max-time 15 "$url" || true
}

emit_stub() {
  local provider="$1"; shift
  local company="$1"; shift
  case "$provider" in
    greenhouse)
      local token="$1"; echo "{ \"company\": \"$company\", \"ats\": \"greenhouse\", \"token\": \"$token\", \"priority\": \"High\" }" ;;
    lever)
      local token="$1"; echo "{ \"company\": \"$company\", \"ats\": \"lever\", \"token\": \"$token\", \"priority\": \"High\" }" ;;
    workable)
      local token="$1"; echo "{ \"company\": \"$company\", \"ats\": \"workable\", \"token\": \"$token\", \"priority\": \"High\" }" ;;
    ashby)
      local token="$1"; token=${token:-<TOKEN>}; echo "{ \"company\": \"$company\", \"ats\": \"ashby\", \"token\": \"$token\", \"priority\": \"High\" }" ;;
    workday)
      local host="$1"; local path="$2"; host=${host:-<HOST>.myworkdayjobs.com}; path=${path:-<PATH>}; echo "{ \"company\": \"$company\", \"ats\": \"workday\", \"host\": \"$host\", \"path\": \"$path\", \"priority\": \"High\" }" ;;
  esac
}

main() {
  local input_url="${1:-}"; local input_name="${2:-}"
  if [[ -z "$input_url" ]]; then
    echo "Usage: $0 <careers-or-root-url> [Company Name]" >&2
    exit 1
  fi
  input_url=$(normalize_url "$input_url")

  # Build candidate URLs to try
  local host root
  host=$(echo "$input_url" | sed -E 's#https?://([^/]+)/?.*#\1#')
  root="https://$host"
  declare -a candidates=("$input_url" "$root" "$root/careers" "$root/jobs" "https://careers.$host" "https://jobs.$host")

  local html="" company_name=""

  # Try HEAD/redirect discovery first
  for url in "${candidates[@]}"; do
    local heads
    heads=$(fetch_heads "$url")
    [[ -z "$heads" ]] && continue
    # Detect ATS in redirect chain
    if echo "$heads" | grep -qiE 'boards\.greenhouse\.io|boards-api\.greenhouse\.io'; then
      echo greenhouse
      # try to pull token from Location
      local token
      token=$(echo "$heads" | grep -Eio 'boards\.greenhouse\.io/[^/ ]+' | head -n1 | cut -d/ -f2)
      [[ -n "$token" ]] && emit_stub greenhouse "${input_name:-<NAME>}" "$token"
      return 0
    fi
    if echo "$heads" | grep -qi 'jobs\.lever\.co'; then
      echo lever
      local token
      token=$(echo "$heads" | grep -Eio 'jobs\.lever\.co/[^/ ]+' | head -n1 | cut -d/ -f2)
      [[ -n "$token" ]] && emit_stub lever "${input_name:-<NAME>}" "$token"
      return 0
    fi
    if echo "$heads" | grep -qiE '\.myworkdayjobs\.com|wd[0-9]*\.myworkdayjobs\.com'; then
      echo workday
      local loc
      loc=$(echo "$heads" | grep -i '^location: ' | tail -n1 | sed -E 's/^[Ll]ocation: //')
      local host2 path2
      host2=$(echo "$loc" | sed -E 's#https?://([^/]+)/.*#\1#')
      path2=$(echo "$loc" | sed -E 's#https?://[^/]+/([^/?]+).*#\1#')
      emit_stub workday "${input_name:-<NAME>}" "$host2" "$path2"
      return 0
    fi
    if echo "$heads" | grep -qi 'workable\.com'; then
      echo workable
      local token
      token=$(echo "$heads" | grep -Eio 'https?://([A-Za-z0-9-]+)\.workable\.com' | head -n1 | sed -E 's#https?://([^./]+)\.workable\.com#\1#')
      [[ -n "$token" ]] && emit_stub workable "${input_name:-<NAME>}" "$token"
      return 0
    fi
    if echo "$heads" | grep -qiE 'jobs\.ashbyhq\.com|/api/org/.*/job-postings'; then
      echo ashby
      local token
      token=$(echo "$heads" | grep -Eio 'jobs\.ashbyhq\.com/(api/org/)?[A-Za-z0-9-]+' | head -n1 | sed -E 's#.*(api/org/)?##')
      emit_stub ashby "${input_name:-<NAME>}" "$token"
      return 0
    fi
  done

  # Fallback to HTML scraping if no redirect-based detection worked
  for url in "${candidates[@]}"; do
    html=$(fetch_html "$url")
    [[ -z "$html" ]] && continue
    # Guess company name from <title>
    if [[ -z "$input_name" ]]; then
      local title
      title=$(echo "$html" | grep -o -m1 '<title>[^<]*' | sed 's/<title>//') || true
      company_name=$(echo "$title" | sed -E 's/( Careers| - Careers| – Careers| \| Careers).*//; s/ +$//')
    else
      company_name="$input_name"
    fi
    [[ -z "$company_name" ]] && company_name="<NAME>"

    if echo "$html" | grep -qE 'boards\.greenhouse\.io|boards-api\.greenhouse\.io'; then
      echo greenhouse
      local token
      token=$(echo "$html" | grep -Eo 'boards\.greenhouse\.io/[^/" ]+' | head -n1 | cut -d/ -f2)
      [[ -n "$token" ]] && emit_stub greenhouse "$company_name" "$token"
      return 0
    fi
    if echo "$html" | grep -q 'jobs.lever.co'; then
      echo lever
      local token
      token=$(echo "$html" | grep -Eo 'jobs\.lever\.co/[^/" ]+' | head -n1 | cut -d/ -f2)
      [[ -n "$token" ]] && emit_stub lever "$company_name" "$token"
      return 0
    fi
    if echo "$html" | grep -qE '\.myworkdayjobs\.com|wd[0-9]*\.myworkdayjobs\.com'; then
      echo workday
      local md_url host path
      md_url=$(echo "$html" | grep -Eo 'https?://[A-Za-z0-9.-]+\.myworkdayjobs\.com/[^" ]+' | head -n1)
      if [[ -n "$md_url" ]]; then
        host=$(echo "$md_url" | sed -E 's#https?://([^/]+)/.*#\1#')
        path=$(echo "$md_url" | sed -E 's#https?://[^/]+/([^/?]+).*#\1#')
      fi
      emit_stub workday "$company_name" "${host:-}" "${path:-}"
      return 0
    fi
    if echo "$html" | grep -qE 'jobs\.ashbyhq\.com|/api/org/.*/job-postings'; then
      echo ashby
      local token
      token=$(echo "$html" | grep -Eo 'jobs\.ashbyhq\.com/(api/org/)?[A-Za-z0-9-]+' | head -n1 | sed -E 's#.*(api/org/)?##')
      emit_stub ashby "$company_name" "$token"
      return 0
    fi
    if echo "$html" | grep -q 'workable.com'; then
      echo workable
      local token
      token=$(echo "$url" | sed -n 's#https\?://\([^./]*\)\.workable\.com.*#\1#p')
      if [[ -z "$token" ]]; then
        token=$(echo "$html" | grep -Eo 'https?://([A-Za-z0-9-]+)\.workable\.com' | head -n1 | sed -E 's#https?://([^./]+)\.workable\.com#\1#')
      fi
      [[ -n "$token" ]] && emit_stub workable "$company_name" "$token"
      return 0
    fi
  done

  echo unknown
  echo "Hints (redirects):" >&2
  fetch_heads "$input_url" | sed -n '1,/$/p' >&2 || true
  echo "Hints (outbound links in HTML):" >&2
  fetch_html "$input_url" | grep -Eo 'https?://[^" ]*(greenhouse|lever|workable|ashbyhq|myworkdayjobs)[^" ]*' | sort -u >&2 || true
  return 1
}

main "$@"
