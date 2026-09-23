// Tiny shared-password gate. The cookie holds a hash of the password, never the password.
export const AUTH_COOKIE = "hunter_auth";

export async function passwordToken(password: string): Promise<string> {
  const data = new TextEncoder().encode(`apartment-hunter:${password}`);
  const digest = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
}
