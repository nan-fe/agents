import { Suspense } from 'react';

import LoginPage from './login-page';

const LoginRoute = () => {
  return (
    <Suspense
      fallback={
        <main className="mx-auto flex min-h-screen w-full max-w-md items-center px-4 py-12">
          <section className="w-full rounded-3xl border border-pink-200 bg-white p-8 text-center text-gray-600">
            正在加载登录页...
          </section>
        </main>
      }
    >
      <LoginPage />
    </Suspense>
  );
};

export default LoginRoute;
