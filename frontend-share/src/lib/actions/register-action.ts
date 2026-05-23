'use server';

import { registerUser } from '@/lib/user-service';

export type RegisterActionState = {
  error: string | null;
  success: boolean;
};

export const registerAction = async (
  _prevState: RegisterActionState,
  formData: FormData,
): Promise<RegisterActionState> => {
  const username = String(formData.get('username') ?? '');
  const password = String(formData.get('password') ?? '');
  const confirmPassword = String(formData.get('confirmPassword') ?? '');
  const name = String(formData.get('name') ?? '');

  if (password !== confirmPassword) {
    return { error: '两次输入的密码不一致。', success: false };
  }

  const result = await registerUser({
    username,
    password,
    name: name.trim() || undefined,
  });

  if (!result.ok) {
    return { error: result.error, success: false };
  }

  return { error: null, success: true };
};
