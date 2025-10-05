namespace LexerModule;

public interface ILexerState
{
    bool CanEnter(Lexer lexer);
    void Enter(Lexer lexer);
    ILexerState Update(Lexer lexer);
}