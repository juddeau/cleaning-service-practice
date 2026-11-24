package cleaning;

import java.io.IOException;
import java.math.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.time.*;
import java.util.*;

/** Object-oriented monthly planning. Requires JDK 17 or newer. */
public final class CleaningApp {
    public record Zone(String type, BigDecimal area) {
        public Zone { if (area.signum() < 0) throw new IllegalArgumentException("Negative area"); }
    }
    public record Office(int id, String client, List<Zone> zones, List<String> services) {
        public Office { zones = List.copyOf(zones); services = List.copyOf(services); }
        BigDecimal area() { return zones.stream().map(Zone::area).reduce(BigDecimal.ZERO, BigDecimal::add); }
    }
    public record Brigade(int id, int capacity) {
        public Brigade { if (capacity < 0) throw new IllegalArgumentException("Negative capacity"); }
    }
    public record Task(LocalDate date, int officeId, String service, int hours100) {
        public Task { if (hours100 < 0) throw new IllegalArgumentException("Negative duration"); }
    }
    public record Assignment(Task task, int brigadeId) { }
    public record Plan(List<Assignment> assigned, List<Task> unassigned) {
        public Plan { assigned = List.copyOf(assigned); unassigned = List.copyOf(unassigned); }
    }
    public interface CalendarPolicy { List<LocalDate> dates(YearMonth month, Set<LocalDate> holidays); }
    public abstract static class CleaningService implements CalendarPolicy {
        private final String code;
        private final BigDecimal rate, minutes;
        protected CleaningService(String code, BigDecimal rate, BigDecimal minutes) {
            if (rate.signum() < 0 || minutes.signum() < 0) throw new IllegalArgumentException("Negative rate or norm");
            this.code = code; this.rate = rate; this.minutes = minutes;
        }
        public String code() { return code; }
        public BigDecimal rate() { return rate; }
        public int duration(Office office) {
            // The Python reference rounds the binary floating-point value.
            double hours = office.area().doubleValue() * minutes.doubleValue() / 100 / 60;
            return new BigDecimal(hours).setScale(2, RoundingMode.HALF_EVEN).movePointRight(2).intValueExact();
        }
        protected abstract boolean accepts(LocalDate date);
        protected boolean firstOnly() { return false; }
        public final List<LocalDate> dates(YearMonth month, Set<LocalDate> holidays) {
            List<LocalDate> result = new ArrayList<>();
            for (int day = 1; day <= month.lengthOfMonth(); day++) {
                LocalDate date = month.atDay(day);
                if (!holidays.contains(date) && accepts(date)) {
                    result.add(date);
                    if (firstOnly()) break;
                }
            }
            return result;
        }
    }
    public static final class DailyService extends CleaningService {
        DailyService(String c, BigDecimal r, BigDecimal m) { super(c,r,m); }
        protected boolean accepts(LocalDate d) { return d.getDayOfWeek().getValue() <= 5; }
    }
    public static final class WeeklyService extends CleaningService {
        WeeklyService(String c, BigDecimal r, BigDecimal m) { super(c,r,m); }
        protected boolean accepts(LocalDate d) { return d.getDayOfWeek() == DayOfWeek.WEDNESDAY; }
    }
    public static final class MonthlyService extends CleaningService {
        MonthlyService(String c, BigDecimal r, BigDecimal m) { super(c,r,m); }
        protected boolean accepts(LocalDate d) { return d.getDayOfWeek() == DayOfWeek.SATURDAY; }
        protected boolean firstOnly() { return true; }
    }
    public interface AssignmentStrategy { Plan assign(List<Task> tasks, List<Brigade> brigades); }
    private record Load(int hours100, int brigadeId, int capacity) { }
    public static final class GreedyAssignment implements AssignmentStrategy {
        public Plan assign(List<Task> tasks, List<Brigade> brigades) {
            if (brigades.stream().map(Brigade::id).distinct().count() != brigades.size())
                throw new IllegalArgumentException("Duplicate brigade id");
            List<Assignment> assigned = new ArrayList<>();
            List<Task> unassigned = new ArrayList<>();
            PriorityQueue<Load> queue = new PriorityQueue<>(Comparator.comparingInt(Load::hours100)
                    .thenComparingInt(Load::brigadeId));
            LocalDate current = null;
            for (Task task : sorted(tasks)) {
                if (!task.date().equals(current)) {
                    current = task.date(); queue.clear();
                    for (Brigade brigade : brigades) queue.add(new Load(0, brigade.id(), brigade.capacity()));
                }
                List<Load> skipped = new ArrayList<>();
                boolean found = false;
                while (!queue.isEmpty()) {
                    Load load = queue.remove();
                    if (load.hours100() + task.hours100() <= load.capacity()) {
                        assigned.add(new Assignment(task, load.brigadeId()));
                        queue.add(new Load(load.hours100() + task.hours100(), load.brigadeId(), load.capacity()));
                        found = true; break;
                    }
                    skipped.add(load);
                }
                queue.addAll(skipped);
                if (!found) unassigned.add(task);
            }
            return new Plan(assigned, unassigned);
        }
    }
    public static final class Planner {
        private final AssignmentStrategy strategy;
        public Planner(AssignmentStrategy strategy) { this.strategy = Objects.requireNonNull(strategy); }
        public List<Task> build(List<Office> offices, Map<String,CleaningService> services,
                                YearMonth month, Set<LocalDate> holidays) {
            List<Task> tasks = new ArrayList<>();
            for (Office office : offices) for (String code : office.services()) {
                CleaningService service = Objects.requireNonNull(services.get(code), "Unknown service");
                for (LocalDate date : service.dates(month, holidays))
                    tasks.add(new Task(date, office.id(), code, service.duration(office)));
            }
            return sorted(tasks);
        }
        public Plan assign(List<Task> tasks, List<Brigade> brigades) { return strategy.assign(tasks, brigades); }
        public BigDecimal cost(Office office, Map<String,CleaningService> services,
                               Map<String,BigDecimal> coefficients, List<Task> tasks) {
            BigDecimal sum = BigDecimal.ZERO;
            for (String code : office.services()) {
                long visits = tasks.stream().filter(t -> t.officeId() == office.id() && t.service().equals(code)).count();
                for (Zone zone : office.zones())
                    sum = sum.add(zone.area().multiply(services.get(code).rate())
                            .multiply(Objects.requireNonNull(coefficients.get(zone.type()), "Unknown zone type"))
                            .multiply(BigDecimal.valueOf(visits)));
            }
            return sum.setScale(2, RoundingMode.HALF_EVEN);
        }
    }
    private static List<Task> sorted(List<Task> tasks) {
        return tasks.stream().sorted(Comparator.comparing(Task::date)
                .thenComparing(Comparator.comparingInt(Task::hours100).reversed())).toList();
    }
    @SuppressWarnings("unchecked")
    private static Map<String,Object> object(Object value) { return (Map<String,Object>) value; }
    @SuppressWarnings("unchecked")
    private static List<Object> array(Object value) { return (List<Object>) value; }
    private static String str(Object value) { return (String) value; }
    private static BigDecimal num(Object value) { return (BigDecimal) value; }
    private static int id(Object value) { return num(value).intValueExact(); }
    private static String hours(int value) { return BigDecimal.valueOf(value, 2).toPlainString(); }
    public static void main(String[] args) throws IOException {
        if (args.length > 4) throw new IllegalArgumentException("Usage: CleaningApp [input.json] [output-dir] [year] [month]");
        Path input = Path.of(args.length > 0 ? args[0] : "data/sample_data.json");
        Path output = Path.of(args.length > 1 ? args[1] : "data/java");
        YearMonth month = YearMonth.of(args.length > 2 ? Integer.parseInt(args[2]) : 2026,
                args.length > 3 ? Integer.parseInt(args[3]) : 11);
        Map<String,Object> data = object(Json.parse(Files.readString(input, StandardCharsets.UTF_8)));
        Map<String,CleaningService> services = new LinkedHashMap<>();
        for (Object item : array(data.get("services"))) {
            Map<String,Object> s = object(item);
            String code = str(s.get("code")); BigDecimal rate = num(s.get("rate")), minutes = num(s.get("minutes_per_100m2"));
            CleaningService service = switch (str(s.get("periodicity"))) {
                case "daily" -> new DailyService(code,rate,minutes);
                case "weekly" -> new WeeklyService(code,rate,minutes);
                case "monthly" -> new MonthlyService(code,rate,minutes);
                default -> throw new IllegalArgumentException("Unknown periodicity");
            };
            if (services.put(code,service) != null) throw new IllegalArgumentException("Duplicate service");
        }
        List<Office> offices = new ArrayList<>();
        for (Object item : array(data.get("objects"))) {
            Map<String,Object> o = object(item); List<Zone> zones = new ArrayList<>();
            for (Object z : array(o.get("zones"))) { Map<String,Object> zone = object(z);
                zones.add(new Zone(str(zone.get("type")), num(zone.get("area")))); }
            offices.add(new Office(id(o.get("id")), str(o.get("client")), zones,
                    array(o.get("services")).stream().map(CleaningApp::str).toList()));
        }
        List<Brigade> brigades = new ArrayList<>();
        for (Object item : array(data.get("brigades"))) { Map<String,Object> b = object(item);
            brigades.add(new Brigade(id(b.get("id")), num(b.get("capacity_hours")).movePointRight(2).intValueExact())); }
        Map<String,BigDecimal> coefficients = new HashMap<>();
        object(data.get("zone_coefficients")).forEach((key,value) -> coefficients.put(key,num(value)));
        Set<LocalDate> holidays = new HashSet<>();
        for (Object h : array(data.get("holidays"))) holidays.add(LocalDate.parse(str(h)));
        Planner planner = new Planner(new GreedyAssignment());
        List<Task> tasks = planner.build(offices, services, month, holidays);
        Plan plan = planner.assign(tasks, brigades);
        Files.createDirectories(output);
        List<String> taskRows = new ArrayList<>(List.of("date;object_id;service;hours"));
        for (Task task : tasks) taskRows.add(task.date()+";"+task.officeId()+";"+task.service()+";"+hours(task.hours100()));
        Files.write(output.resolve("tasks.csv"),taskRows,StandardCharsets.UTF_8);
        List<String> rows = new ArrayList<>(List.of("Дата;Объект;Услуга;Часы;Бригада"));
        for (Assignment a : plan.assigned()) { Task t = a.task();
            rows.add(t.date()+";"+t.officeId()+";"+t.service()+";"+hours(t.hours100())+";"+a.brigadeId()); }
        Files.write(output.resolve("schedule.csv"),rows,StandardCharsets.UTF_8);
        List<String> costs = new ArrayList<>(List.of("object_id;cost"));
        BigDecimal total = BigDecimal.ZERO;
        for (Office office : offices) { BigDecimal cost = planner.cost(office,services,coefficients,tasks);
            total = total.add(cost); costs.add(office.id()+";"+cost);
            System.out.println(office.client()+": "+cost+" руб."); }
        Files.write(output.resolve("costs.csv"),costs,StandardCharsets.UTF_8);
        System.out.printf("Total: %s; tasks: %d; assigned: %d; unassigned: %d%n",total,tasks.size(),plan.assigned().size(),plan.unassigned().size());
        List<String> missed = new ArrayList<>(List.of("date;object_id;service;hours"));
        for (Task task : plan.unassigned()) missed.add(task.date()+";"+task.officeId()+";"+task.service()+";"+hours(task.hours100()));
        Files.write(output.resolve("unassigned.csv"),missed,StandardCharsets.UTF_8);
    }
}
