namespace LexerModule;

public interface ITokenReader
{
    bool TryStartReading(Lexer lexer);
    Token FinishReading(Lexer lexer);
}