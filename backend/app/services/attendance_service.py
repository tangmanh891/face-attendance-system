"""Attendance Service - Dịch vụ quản lý điểm danh."""
import logging
import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.attendance import Attendance, AttendanceStatus
from app.models.user import User
from app.schemas.attendance import AttendanceStats

logger = logging.getLogger(__name__)

# Cache để theo dõi cooldown check-in (user_id -> thời gian check-in gần nhất)
_checkin_cooldown: dict[str, datetime] = {}
_COOLDOWN_MAX_SIZE = 10000


def _app_timezone() -> ZoneInfo:
    """Timezone cấu hình cho nghiệp vụ điểm danh."""
    try:
        return ZoneInfo(settings.timezone)
    except ZoneInfoNotFoundError:
        logger.warning("Timezone không hợp lệ '%s', fallback UTC", settings.timezone)
        return ZoneInfo("UTC")


def _now() -> datetime:
    """Thời gian hiện tại theo timezone ứng dụng."""
    return datetime.now(_app_timezone())


def _today() -> date:
    """Ngày hiện tại theo timezone ứng dụng."""
    return _now().date()


class AttendanceService:
    """Dịch vụ xử lý logic điểm danh."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def _determine_status(self, check_in_time: datetime) -> AttendanceStatus:
        """Xác định trạng thái điểm danh dựa trên giờ check-in.

        Args:
            check_in_time: Thời gian check-in

        Returns:
            AttendanceStatus (ON_TIME hoặc LATE)
        """
        work_start = datetime.strptime(settings.work_start_time, "%H:%M").time()
        late_threshold = timedelta(minutes=settings.late_threshold_minutes)

        local_check_in = (
            check_in_time.astimezone(_app_timezone())
            if check_in_time.tzinfo
            else check_in_time.replace(tzinfo=_app_timezone())
        )
        work_start_dt = datetime.combine(local_check_in.date(), work_start, tzinfo=_app_timezone())
        deadline = work_start_dt + late_threshold

        if local_check_in <= deadline:
            return AttendanceStatus.ON_TIME
        return AttendanceStatus.LATE

    def _is_in_cooldown(self, user_id: str) -> bool:
        """Kiểm tra xem nhân viên có đang trong thời gian cooldown không."""
        if user_id not in _checkin_cooldown:
            return False

        last_checkin = _checkin_cooldown[user_id]
        cooldown = timedelta(minutes=settings.checkin_cooldown_minutes)
        now = _now()
        if now - last_checkin >= cooldown:
            del _checkin_cooldown[user_id]
            return False
        return True

    def _set_cooldown(self, user_id: str) -> None:
        """Đặt thời gian cooldown cho nhân viên."""
        # Dọn dẹp entries hết hạn khi cache quá lớn
        if len(_checkin_cooldown) > _COOLDOWN_MAX_SIZE:
            cooldown = timedelta(minutes=settings.checkin_cooldown_minutes)
            now = _now()
            expired = [k for k, v in _checkin_cooldown.items() if now - v >= cooldown]
            for k in expired:
                del _checkin_cooldown[k]
        _checkin_cooldown[user_id] = _now()

    async def check_in(
        self,
        user_id: uuid.UUID,
        confidence_score: float,
        captured_image_path: str | None = None,
        notes: str | None = None,
    ) -> Attendance:
        """Thực hiện check-in cho nhân viên.

        Args:
            user_id: ID nhân viên
            confidence_score: Điểm tin cậy nhận diện
            captured_image_path: Đường dẫn ảnh chụp
            notes: Ghi chú

        Returns:
            Bản ghi Attendance mới
        """
        user_id_str = str(user_id)
        today = _today()
        now = _now()

        # Kiểm tra cooldown
        if self._is_in_cooldown(user_id_str):
            remaining = settings.checkin_cooldown_minutes * 60 - (
                _now() - _checkin_cooldown[user_id_str]
            ).seconds
            raise ValueError(
                f"Đã check-in gần đây. Vui lòng đợi {remaining} giây nữa."
            )

        # Kiểm tra đã check-in hôm nay chưa
        existing = await self.db.execute(
            select(Attendance).where(
                and_(
                    Attendance.user_id == user_id,
                    Attendance.date == today,
                )
            )
        )
        existing_record = existing.scalar_one_or_none()

        if existing_record and existing_record.check_in_time is not None:
            # Đã check-in rồi, cập nhật cooldown và báo lỗi
            self._set_cooldown(user_id_str)
            raise ValueError("Nhân viên đã check-in hôm nay rồi.")

        # Xác định trạng thái
        status = self._determine_status(now)

        if existing_record:
            # Cập nhật bản ghi hiện có
            existing_record.check_in_time = now
            existing_record.confidence_score = confidence_score
            existing_record.captured_image_path = captured_image_path
            existing_record.status = status
            existing_record.notes = notes
            attendance = existing_record
        else:
            # Tạo bản ghi mới
            attendance = Attendance(
                user_id=user_id,
                date=today,
                check_in_time=now,
                confidence_score=confidence_score,
                captured_image_path=captured_image_path,
                status=status,
                notes=notes,
            )
            self.db.add(attendance)

        await self.db.flush()

        # Đặt cooldown
        self._set_cooldown(user_id_str)

        logger.info(
            f"Check-in thành công: user={user_id}, status={status}, "
            f"confidence={confidence_score:.3f}"
        )
        return attendance

    async def check_out(
        self,
        user_id: uuid.UUID,
        captured_image_path: str | None = None,
    ) -> Attendance:
        """Thực hiện check-out cho nhân viên.

        Args:
            user_id: ID nhân viên
            captured_image_path: Đường dẫn ảnh chụp

        Returns:
            Bản ghi Attendance đã cập nhật
        """
        today = _today()

        # Tìm bản ghi check-in hôm nay
        result = await self.db.execute(
            select(Attendance).where(
                and_(
                    Attendance.user_id == user_id,
                    Attendance.date == today,
                    Attendance.check_in_time.is_not(None),
                )
            )
        )
        attendance = result.scalar_one_or_none()

        if not attendance:
            raise ValueError("Chưa có bản ghi check-in hôm nay.")

        if attendance.check_out_time is not None:
            raise ValueError("Đã check-out rồi.")

        # Kiểm tra có về sớm không
        now = _now()
        work_end = datetime.strptime(settings.work_end_time, "%H:%M").time()
        work_end_dt = datetime.combine(today, work_end, tzinfo=_app_timezone())

        if now < work_end_dt:
            attendance.status = AttendanceStatus.EARLY_LEAVE

        attendance.check_out_time = now
        if captured_image_path:
            attendance.captured_image_path = captured_image_path

        await self.db.flush()

        logger.info(f"Check-out thành công: user={user_id}")
        return attendance

    async def get_today_attendance(self) -> list[dict]:
        """Lấy danh sách điểm danh hôm nay."""
        today = _today()

        result = await self.db.execute(
            select(Attendance, User)
            .join(User, Attendance.user_id == User.id)
            .where(Attendance.date == today)
            .order_by(Attendance.check_in_time.desc())
        )

        records = []
        for attendance, user in result.all():
            records.append({
                "id": attendance.id,
                "user_id": attendance.user_id,
                "employee_id": user.employee_id,
                "full_name": user.full_name,
                "department": user.department,
                "check_in_time": attendance.check_in_time,
                "check_out_time": attendance.check_out_time,
                "confidence_score": attendance.confidence_score,
                "status": attendance.status,
                "date": attendance.date,
                "notes": attendance.notes,
                "captured_image_path": attendance.captured_image_path,
                "created_at": attendance.created_at,
            })
        return records

    async def get_attendance_stats(self) -> AttendanceStats:
        """Lấy thống kê điểm danh tổng quan."""
        today = _today()

        # Tổng nhân viên active
        total_result = await self.db.execute(
            select(func.count(User.id)).where(User.is_active == True)  # noqa: E712
        )
        total_employees = total_result.scalar() or 0

        # Điểm danh hôm nay
        today_result = await self.db.execute(
            select(Attendance.status, func.count(Attendance.id))
            .where(Attendance.date == today)
            .group_by(Attendance.status)
        )
        today_stats = dict(today_result.all())

        present_today = sum(
            today_stats.get(s, 0)
            for s in [AttendanceStatus.ON_TIME, AttendanceStatus.LATE, AttendanceStatus.EARLY_LEAVE]
        )
        late_today = today_stats.get(AttendanceStatus.LATE, 0)
        absent_today = max(0, total_employees - present_today)

        on_time_rate = (
            today_stats.get(AttendanceStatus.ON_TIME, 0) / present_today * 100
            if present_today > 0
            else 0.0
        )

        # Dữ liệu tuần (7 ngày gần nhất)
        weekly_data = []
        for i in range(6, -1, -1):
            day = today - timedelta(days=i)
            day_result = await self.db.execute(
                select(Attendance.status, func.count(Attendance.id))
                .where(Attendance.date == day)
                .group_by(Attendance.status)
            )
            day_stats = dict(day_result.all())
            weekly_data.append({
                "date": day.isoformat(),
                "on_time": day_stats.get(AttendanceStatus.ON_TIME, 0),
                "late": day_stats.get(AttendanceStatus.LATE, 0),
                "absent": max(0, total_employees - sum(day_stats.values())),
            })

        # Dữ liệu tháng (30 ngày gần nhất)
        monthly_data = []
        for i in range(29, -1, -1):
            day = today - timedelta(days=i)
            day_result = await self.db.execute(
                select(func.count(Attendance.id))
                .where(Attendance.date == day)
            )
            count = day_result.scalar() or 0
            monthly_data.append({
                "date": day.isoformat(),
                "count": count,
            })

        return AttendanceStats(
            total_employees=total_employees,
            present_today=present_today,
            late_today=late_today,
            absent_today=absent_today,
            on_time_rate=round(on_time_rate, 1),
            weekly_data=weekly_data,
            monthly_data=monthly_data,
        )
