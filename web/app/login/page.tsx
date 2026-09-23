import { login } from "../actions";

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const params = await searchParams;
  const next = typeof params.next === "string" ? params.next : "/";
  return (
    <main className="mx-auto flex min-h-screen max-w-sm flex-col justify-center px-4">
      <h1 className="mb-6 text-2xl font-semibold">Apartment Hunter</h1>
      <form action={login} className="space-y-3">
        <input type="hidden" name="next" value={next} />
        <input
          type="password"
          name="password"
          placeholder="Contraseña"
          autoFocus
          required
          className="w-full rounded-lg border border-line bg-card px-3 py-2"
        />
        {params.error && <p className="text-sm text-red-600">Contraseña incorrecta.</p>}
        <button className="w-full rounded-lg bg-accent px-3 py-2 font-medium text-white dark:text-black">
          Entrar
        </button>
      </form>
    </main>
  );
}
