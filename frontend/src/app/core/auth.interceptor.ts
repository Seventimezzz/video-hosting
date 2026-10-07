import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, switchMap, throwError } from 'rxjs';

import { AuthService } from './auth.service';

// На эти адреса 401 — ожидаемый ответ, refresh не поможет.
const NO_REFRESH_URLS = ['/api/login', '/api/register', '/api/refresh', '/api/logout'];

/**
 * Access-токен живёт 15 минут. Когда API отвечает 401, пробуем один раз обновить
 * пару токенов через /api/refresh и повторить исходный запрос.
 */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);

  return next(req).pipe(
    catchError((err: unknown) => {
      const isRefreshable =
        err instanceof HttpErrorResponse &&
        err.status === 401 &&
        req.url.startsWith('/api/') &&
        !NO_REFRESH_URLS.includes(req.url);

      if (!isRefreshable) {
        return throwError(() => err);
      }

      return auth.refresh().pipe(
        catchError(() => {
          auth.markLoggedOut();
          return throwError(() => err);
        }),
        switchMap(() => next(req)),
      );
    }),
  );
};
