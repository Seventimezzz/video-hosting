import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { AuthService } from './auth.service';

export const authGuard: CanActivateFn = async (_route, state) => {
  const auth = inject(AuthService);
  const router = inject(Router);

  const user = await auth.ensureLoaded();
  return user ? true : router.createUrlTree(['/login'], { queryParams: { next: state.url } });
};
