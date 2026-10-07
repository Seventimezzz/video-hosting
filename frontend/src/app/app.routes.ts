import { Routes } from '@angular/router';

import { authGuard } from './core/auth.guard';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'videos' },
  {
    path: 'login',
    loadComponent: () => import('./pages/login/login').then((m) => m.Login),
  },
  {
    path: 'videos',
    loadComponent: () => import('./pages/video-list/video-list').then((m) => m.VideoList),
  },
  {
    path: 'videos/:id',
    // Отдельный lazy-чанк: hls.js (~400 КБ) грузится только на странице плеера.
    loadComponent: () => import('./pages/video-player/video-player').then((m) => m.VideoPlayer),
  },
  {
    path: 'upload',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/upload/upload').then((m) => m.Upload),
  },
  { path: '**', redirectTo: 'videos' },
];
