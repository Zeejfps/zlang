namespace LexerModule;

public interface ILexerState
{
    bool TryStartReading(Lexer lexer);
    Token FinishReading(Lexer lexer);
}