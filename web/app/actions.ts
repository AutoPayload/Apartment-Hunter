"use server";

import { cookies } from "next/headers";
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { AUTH_COOKIE, passwordToken } from "@/lib/auth";
import { db } from "@/lib/supabase";
import { STATUSES, type Status } from "@/lib/types";

async function assertAuthed() {
  const password = process.env.DASHBOARD_PASSWORD;
  if (!password) return;
  const token = (await cookies()).get(AUTH_COOKIE)?.value;
  if (token !== (await passwordToken(password))) throw new Error("Not authorized");
}

export async function setStatus(id: number, status: Status) {
  await assertAuthed();
  if (!Number.isInteger(id) || !STATUSES.includes(status)) throw new Error("Invalid input");
  const { error } = await db().from("listings").update({ status }).eq("id", id);
  if (error) throw new Error(error.message);
  revalidatePath("/");
}

export async function login(formData: FormData) {
  const password = process.env.DASHBOARD_PASSWORD;
  const given = String(formData.get("password") ?? "");
  const next = String(formData.get("next") ?? "/");
  if (!password || given !== password) redirect("/login?error=1");
  (await cookies()).set(AUTH_COOKIE, await passwordToken(password), {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge: 60 * 60 * 24 * 90,
    path: "/",
  });
  redirect(next.startsWith("/") && !next.startsWith("//") ? next : "/");
}
