export interface UserOut {
  id: number
  username: string | null
  full_name: string
  is_admin: boolean
  is_bootstrap: boolean
  max_concurrent_gpus: number
}

export interface ServerOut {
  id: number
  name: string
  is_active: boolean
}

export interface GpuOut {
  id: number
  server_id: number
  index_on_server: number
  model_name: string
  total_ram_mb: number
  is_active: boolean
}

/** A GPU's live occupancy "right now" — powers the Reserve page availability glance. */
export interface GpuOverviewOut {
  id: number
  index_on_server: number
  model_name: string
  total_ram_mb: number
  used_ram_mb: number
  free_ram_mb: number
  active_reservations: number
  is_active: boolean
}

export interface ServerOverviewOut {
  id: number
  name: string
  is_active: boolean
  gpus: GpuOverviewOut[]
}

export interface RegulationOut {
  max_ram_per_reservation_gb: number
  max_duration_hours: number
  booking_horizon_days: number
  min_reservation_slot_minutes: number
  max_active_reservations_per_user: number
  reactivation_delay_minutes: number
  timezone: string
}

// Student-facing -- deliberately has no `description` field; only admins can see what a
// reservation is for (see AdminReservationOut).
export interface ReservationOut {
  id: number
  gpu_id: number
  user_id: number
  start_time: string
  end_time: string
  ram_mb: number
  status: string
  created_at: string
}

// Student-facing -- no `description`, same reasoning as ReservationOut.
export interface WatchOut {
  id: number
  gpu_id: number
  range_start: string
  range_end: string
  min_ram_needed_mb: number
  auto_book: boolean
  is_active: boolean
  created_at: string
}

export interface OccupancyBucket {
  start: string
  end: string
  usage: Record<string, number>
}

export interface OccupancySegment {
  start: string
  end: string
  user: string
  ram_mb: number
  reservation_id: number
  cancelled: boolean
}

export interface OccupancyChartData {
  range_start: string
  range_end: string
  capacity_mb: number
  tz: string
  bucket_minutes: number
  buckets: OccupancyBucket[]
  segments: OccupancySegment[]
}

export interface FreeRamOut {
  free_ram_mb: number
}

export interface UserAdminOut {
  id: number
  username: string | null
  full_name: string
  is_active: boolean
  is_admin: boolean
  is_bootstrap: boolean
  max_concurrent_gpus: number
  server_ids: number[]
}

export interface BulkUserCreateItem {
  username: string
  password: string
  full_name: string
  max_concurrent_gpus?: number
  server_ids?: number[]
}

export interface BulkUserCreateResultItem {
  username: string
  success: boolean
  user_id: number | null
  error: string | null
}

export interface ServerAdminOut {
  id: number
  name: string
  is_active: boolean
}

export interface GpuAdminOut {
  id: number
  server_id: number
  index_on_server: number
  model_name: string
  total_ram_mb: number
  is_active: boolean
}

export interface AdminReservationOut {
  id: number
  gpu_id: number
  user_id: number
  user_full_name: string
  server_name: string
  gpu_index: number
  start_time: string
  end_time: string
  ram_mb: number
  description: string | null
  status: string
}

export interface AdminReservationListOut {
  items: AdminReservationOut[]
  total: number
  page: number
  page_size: number
}

export interface AdminWatchOut {
  id: number
  gpu_id: number
  user_id: number
  user_full_name: string
  server_name: string
  gpu_index: number
  range_start: string
  range_end: string
  min_ram_needed_mb: number
  description: string | null
  auto_book: boolean
  status: string
}

export interface AdminWatchListOut {
  items: AdminWatchOut[]
  total: number
  page: number
  page_size: number
}


export type FeedbackCategory = 'BUG' | 'PROBLEM' | 'SUGGESTION' | 'OTHER'

// Own submitted feedback -- visible to the submitting student, never to other students.
export interface FeedbackOut {
  id: number
  category: FeedbackCategory
  message: string
  created_at: string
}

export interface AdminFeedbackOut {
  id: number
  user_id: number
  user_full_name: string
  category: FeedbackCategory
  message: string
  created_at: string
}

export interface AdminFeedbackListOut {
  items: AdminFeedbackOut[]
  total: number
  page: number
  page_size: number
}

export interface NotificationOut {
  id: number
  message: string
  created_at: string
}

export interface RankedUsageOut {
  metric: string
  unit: string
  labels: string[]
  values: number[]
}
