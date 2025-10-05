namespace LexerModule;

public interface ILexerState
{
    bool TryStartReading(Lexer lexer);
    TokenKind FinishReading(Lexer lexer);
}