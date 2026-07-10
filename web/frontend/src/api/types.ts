export interface UserOut {
  id: number
  username: string | null
  full_name: string
  student_id: string | null
  is_admin: boolean
  max_concurrent_gpus: number
}

export interface ServerOut {
  id: number
  name: string
  description: string | null
}

export interface GpuOut {
  id: number
  server_id: number
  index_on_server: number
  model_name: string
  total_ram_mb: number
}

export interface RegulationOut {
  max_ram_per_reservation_mb: number
  max_duration_hours: number
  booking_horizon_days: number
  min_reservation_slot_minutes: number
  max_active_reservations_per_user: number
  min_cancellation_notice_minutes: number
  timezone: string
}

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
}

export interface OccupancyChartData {
  range_start: string
  range_end: string
  capacity_mb: number
  tz: string
  bucket_hours: number
  buckets: OccupancyBucket[]
  segments: OccupancySegment[]
}

export interface UserAdminOut {
  id: number
  username: string | null
  full_name: string
  student_id: string | null
  is_active: boolean
  is_admin: boolean
  max_concurrent_gpus: number
  server_ids: number[]
}

export interface BulkUserCreateItem {
  username: string
  password: string
  full_name: string
  student_id?: string | null
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
  description: string | null
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
  status: string
}

export interface UserWithReservationsOut {
  id: number
  full_name: string
}

export interface RankedUsageOut {
  metric: string
  unit: string
  labels: string[]
  values: number[]
}
