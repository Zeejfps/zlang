namespace LexerModule;

public static class Lexer
{
    public static IEnumerable<Token> Tokenize(string empty)
    {
        using var reader = new StringReader(empty);
        return Tokenize(reader);
    }

    public static IEnumerable<Token> Tokenize(TextReader reader)
    {
        yield break;
    }
}