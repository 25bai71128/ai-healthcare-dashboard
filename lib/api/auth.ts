import { requireAuthSession } from "@/lib/auth";
import { ApiError } from "@/lib/api/http";

export async function requireUserId(): Promise<string> {
  const session = await requireAuthSession();
  const userId = session.user?.id;

  if (!userId) {
    throw new ApiError(401, "UNAUTHORIZED", "Authentication required.");
  }

  return userId;
}
