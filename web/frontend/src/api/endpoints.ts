import { api } from './client'
import type {
  AdminReservationOut,
  BulkUserCreateItem,
  BulkUserCreateResultItem,
  GpuAdminOut,
  GpuOut,
  OccupancyChartData,
  RankedUsageOut,
  RegulationOut,
  ReservationOut,
  ServerAdminOut,
  ServerOut,
  UserAdminOut,
  UserOut,
  UserWithReservationsOut,
  WatchOut,
} from './types'

export const authApi = {
  login: (username: string, password: string) =>
    api.post<{ access_token: string; token_type: string }>('/api/auth/login', { username, password }),
  me: () => api.get<UserOut>('/api/auth/me'),
  changePassword: (old_password: string, new_password: string) =>
    api.post<void>('/api/auth/change-password', { old_password, new_password }),
}

export const scheduleApi = {
  regulation: () => api.get<RegulationOut>('/api/regulation'),
  servers: () => api.get<ServerOut[]>('/api/servers'),
  gpus: (serverId: number) => api.get<GpuOut[]>(`/api/servers/${serverId}/gpus`),
  availability: (gpuId: number, rangeStart: string, rangeEnd: string, bucketHours?: number) =>
    api.get<OccupancyChartData>(`/api/gpus/${gpuId}/availability`, {
      range_start: rangeStart,
      range_end: rangeEnd,
      bucket_hours: bucketHours,
    }),
}

export const reservationsApi = {
  list: (upcomingOnly = true) => api.get<ReservationOut[]>('/api/reservations', { upcoming_only: upcomingOnly }),
  create: (gpu_id: number, start_time: string, end_time: string, ram_mb: number) =>
    api.post<ReservationOut>('/api/reservations', { gpu_id, start_time, end_time, ram_mb }),
  cancel: (id: number) => api.delete<void>(`/api/reservations/${id}`),
}

export const watchesApi = {
  list: () => api.get<WatchOut[]>('/api/watches'),
  create: (gpu_id: number, range_start: string, range_end: string, min_ram_needed_mb: number) =>
    api.post<WatchOut>('/api/watches', { gpu_id, range_start, range_end, min_ram_needed_mb }),
  cancel: (id: number) => api.delete<void>(`/api/watches/${id}`),
}

export const adminUsersApi = {
  list: () => api.get<UserAdminOut[]>('/api/admin/users'),
  bulkCreate: (users: BulkUserCreateItem[]) =>
    api.post<{ results: BulkUserCreateResultItem[] }>('/api/admin/users/bulk', { users }),
  rename: (id: number, full_name: string) => api.patch<UserAdminOut>(`/api/admin/users/${id}/rename`, { full_name }),
  setActive: (id: number, is_active: boolean) =>
    api.patch<UserAdminOut>(`/api/admin/users/${id}/active`, { is_active }),
  setAdmin: (id: number, is_admin: boolean) => api.patch<UserAdminOut>(`/api/admin/users/${id}/admin`, { is_admin }),
  setMaxConcurrentGpus: (id: number, max_concurrent_gpus: number) =>
    api.patch<UserAdminOut>(`/api/admin/users/${id}/max-concurrent-gpus`, { max_concurrent_gpus }),
  setServerAccess: (id: number, server_ids: number[]) =>
    api.patch<UserAdminOut>(`/api/admin/users/${id}/server-access`, { server_ids }),
  resetPassword: (id: number, new_password: string) =>
    api.post<void>(`/api/admin/users/${id}/reset-password`, { new_password }),
  delete: (id: number) => api.delete<void>(`/api/admin/users/${id}`),
}

export const adminServersApi = {
  list: () => api.get<ServerAdminOut[]>('/api/admin/servers'),
  create: (name: string, description?: string) => api.post<ServerAdminOut>('/api/admin/servers', { name, description }),
  rename: (id: number, name: string) => api.patch<ServerAdminOut>(`/api/admin/servers/${id}/rename`, { name }),
  setActive: (id: number, is_active: boolean) =>
    api.patch<ServerAdminOut>(`/api/admin/servers/${id}/active`, { is_active }),
  delete: (id: number) => api.delete<void>(`/api/admin/servers/${id}`),
  gpus: (serverId: number) => api.get<GpuAdminOut[]>(`/api/admin/servers/${serverId}/gpus`),
  addGpu: (serverId: number, index_on_server: number, model_name: string, total_ram_mb: number) =>
    api.post<GpuAdminOut>(`/api/admin/servers/${serverId}/gpus`, { index_on_server, model_name, total_ram_mb }),
  renameGpu: (gpuId: number, model_name: string) => api.patch<GpuAdminOut>(`/api/admin/gpus/${gpuId}/rename`, { model_name }),
  setGpuActive: (gpuId: number, is_active: boolean) =>
    api.patch<GpuAdminOut>(`/api/admin/gpus/${gpuId}/active`, { is_active }),
  deleteGpu: (gpuId: number) => api.delete<void>(`/api/admin/gpus/${gpuId}`),
}

export const adminRegulationApi = {
  get: () => api.get<RegulationOut>('/api/admin/regulation'),
  update: (payload: RegulationOut) => api.put<RegulationOut>('/api/admin/regulation', payload),
}

export const adminReservationsApi = {
  list: (userId?: number) => api.get<AdminReservationOut[]>('/api/admin/reservations', { user_id: userId }),
  usersWithReservations: () => api.get<UserWithReservationsOut[]>('/api/admin/reservations/users-with-reservations'),
  cancel: (id: number) => api.delete<void>(`/api/admin/reservations/${id}`),
  cancelForUser: (userId: number) =>
    api.post<{ cancelled: number }>(`/api/admin/reservations/cancel-for-user/${userId}`),
  cancelAll: (confirmPhrase: string) =>
    api.post<{ cancelled: number }>('/api/admin/reservations/cancel-all', { confirm_phrase: confirmPhrase }),
}

export const adminUsageApi = {
  ranked: (rangeStart: string, rangeEnd: string, metric: 'gpu_hours' | 'ram_gb_hours') =>
    api.get<RankedUsageOut>('/api/admin/usage/ranked', { range_start: rangeStart, range_end: rangeEnd, metric }),
  historicalAvailability: (gpuId: number, startDate: string, days: number) =>
    api.get<OccupancyChartData>('/api/admin/usage/historical-availability', {
      gpu_id: gpuId,
      start_date: startDate,
      days,
    }),
}
