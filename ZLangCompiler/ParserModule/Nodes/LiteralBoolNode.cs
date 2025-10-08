using LexerModule;

namespace ParserModule.Nodes;

public sealed class LiteralBoolNode : AstNode
{
    public Token Token { get; }
    public bool Value { get; }

    public LiteralBoolNode(Token token)
    {
        Token = token;
        Value = bool.Parse(token.Lexeme);
    }
    
    public override void Accept(IAstNodeVisitor visitor)
    {
        visitor.VisitLiteralBoolNode(this);
    }
}