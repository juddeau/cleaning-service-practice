package cleaning;

import java.util.*;

/** Small strict JSON reader for the shared UTF-8 educational fixture. */
final class Json {
    private final String text;
    private int pos;
    private Json(String text) { this.text = text; }
    static Object parse(String text) {
        Json parser = new Json(text);
        Object result = parser.value();
        parser.space();
        if (parser.pos != text.length()) throw parser.error();
        return result;
    }
    private IllegalArgumentException error() {
        return new IllegalArgumentException("Invalid JSON at offset " + pos);
    }
    private void space() {
        while (pos < text.length() && " \r\n\t".indexOf(text.charAt(pos)) >= 0) pos++;
    }
    private char take() {
        if (pos == text.length()) throw error();
        return text.charAt(pos++);
    }
    private Object value() {
        space();
        if (pos == text.length()) throw error();
        char c = text.charAt(pos);
        if (c == '"') return string();
        if (c == '{') {
            pos++;
            Map<String,Object> result = new LinkedHashMap<>();
            space();
            if (pos < text.length() && text.charAt(pos) == '}') { pos++; return result; }
            while (true) {
                space();
                if (pos == text.length() || text.charAt(pos) != '"') throw error();
                String key = string(); space();
                if (take() != ':') throw error();
                if (result.containsKey(key)) throw error();
                result.put(key, value()); space();
                char end = take();
                if (end == '}') return result;
                if (end != ',') throw error();
            }
        }
        if (c == '[') {
            pos++;
            List<Object> result = new ArrayList<>(); space();
            if (pos < text.length() && text.charAt(pos) == ']') { pos++; return result; }
            while (true) {
                result.add(value()); space();
                char end = take();
                if (end == ']') return result;
                if (end != ',') throw error();
            }
        }
        for (String literal : List.of("true", "false", "null")) {
            if (text.startsWith(literal, pos)) {
                pos += literal.length();
                return literal.equals("null") ? null : Boolean.valueOf(literal);
            }
        }
        int start = pos;
        while (pos < text.length() && "-+0123456789.eE".indexOf(text.charAt(pos)) >= 0) pos++;
        String number = text.substring(start, pos);
        if (!number.matches("-?(0|[1-9][0-9]*)(\\.[0-9]+)?([eE][+-]?[0-9]+)?")) throw error();
        return new java.math.BigDecimal(number);
    }
    private String string() {
        if (take() != '"') throw error();
        StringBuilder result = new StringBuilder();
        while (true) {
            char c = take();
            if (c == '"') return result.toString();
            if (c < 32) throw error();
            if (c != '\\') { result.append(c); continue; }
            char e = take();
            switch (e) {
                case '"', '\\', '/' -> result.append(e);
                case 'b' -> result.append('\b');
                case 'f' -> result.append('\f');
                case 'n' -> result.append('\n');
                case 'r' -> result.append('\r');
                case 't' -> result.append('\t');
                case 'u' -> {
                    if (pos + 4 > text.length()) throw error();
                    result.append((char) Integer.parseInt(text.substring(pos, pos + 4), 16));
                    pos += 4;
                }
                default -> throw error();
            }
        }
    }
}
