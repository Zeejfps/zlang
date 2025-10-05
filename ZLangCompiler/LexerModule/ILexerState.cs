namespace LexerModule;

public interface ILexerState
{
    bool TryEnter(Lexer lexer);
    ILexerState? Update(Lexer lexer);
}